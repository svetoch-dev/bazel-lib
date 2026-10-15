"""Restore a PostgreSQL backup into a temporary cluster and run a query."""

import argparse
import re
import sys
import time
import uuid
from datetime import datetime

from kubernetes.client.exceptions import ApiException

from rod.libs.py.k8s.api import KubernetesApi, error_details
from rod.libs.py.k8s.postgres import KubernetesPostgresApi
from rod.libs.py.tf.tfvars import Env, formatted_tfvars
from rod.libs.py.utils.logger import CliLogger


logger = CliLogger("rod.scripts.pg.backup_restore.backup_restore")
RUN_ID_LABEL = "backup-restore-run-id"
DEFAULT_K8S_RESOURCE_POLL_INTERVAL_SECONDS = 5
DEFAULT_POSTGRES_RECOVERY_POLL_INTERVAL_SECONDS = 3
TIMESTAMP_FORMAT_ERROR = (
    "expected YYYY-MM-DDTHH:MM:SS with an optional fraction and timezone, "
    "or YYYY.MM.DD HH:MM:SS"
)

# Named groups make it clear which parts are normalized or kept as provided.
# The date separator backreference requires both separators to match.
ISO_TIMESTAMP_PATTERN = re.compile(
    r"^(?P<date>\d{4}(?P<date_separator>[-.])\d{2}(?P=date_separator)\d{2})[Tt ]"
    r"(?P<time>\d{2}:\d{2}:\d{2})"
    r"(?P<fraction>\.\d+)?"
    r"(?P<offset>Z|z|[+-]\d{2}:\d{2})?$"
)


def positive_seconds(value: str) -> int:
    try:
        seconds = int(value)
    except ValueError:
        pass
    else:
        if seconds > 0:
            return seconds

    raise argparse.ArgumentTypeError("must be a positive whole number of seconds")


def parse_timestamp(value: str) -> str:
    """Normalize supported timestamps while preserving fractional seconds."""
    timestamp = " ".join(value.split())
    match = ISO_TIMESTAMP_PATTERN.fullmatch(timestamp)
    if match is None:
        raise argparse.ArgumentTypeError(TIMESTAMP_FORMAT_ERROR)

    parts = match.groupdict()
    date = parts["date"].replace(".", "-")
    time = parts["time"]
    fraction = parts["fraction"] or ""
    offset = parts["offset"] or "+00:00"
    if offset.lower() == "z":
        offset = "+00:00"

    try:
        # datetime validates the timestamp but stores only six fraction digits.
        # Validate a six-digit prefix and return the full original fraction below.
        datetime.fromisoformat(f"{date}T{time}{fraction[:7]}{offset}")
    except ValueError as error:
        raise argparse.ArgumentTypeError(TIMESTAMP_FORMAT_ERROR) from error

    return f"{date}T{time}{fraction}{offset}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Restore a PostgreSQL cluster backup into a temporary cluster, "
            "run a SQL query, and remove the temporary cluster."
        )
    )
    parser.add_argument(
        "--postgres",
        required=True,
        help="exact source PostgreSQL cluster name (metadata.name)",
    )
    parser.add_argument(
        "--namespace",
        help="limit source cluster lookup and create the clone in this namespace",
    )
    parser.add_argument(
        "--environment",
        required=True,
        type=parse_environment,
        metavar="ENVIRONMENT",
        help="environment key from terraform.tfvars.json",
    )
    parser.add_argument(
        "--database",
        required=True,
        help="database for the query",
    )
    parser.add_argument(
        "--date",
        required=True,
        nargs="+",
        help=(
            "point-in-time recovery target; accepts the form "
            "'2024.01.07 00:00:00' or an ISO timestamp. Missing timezone is UTC."
        ),
    )
    parser.add_argument("--query", required=True, help="SQL query to run on the clone")
    parser.add_argument(
        "--k8s-resource-poll-interval-seconds",
        type=positive_seconds,
        default=DEFAULT_K8S_RESOURCE_POLL_INTERVAL_SECONDS,
        help=(
            "seconds between Kubernetes resource readiness and cleanup checks "
            f"(default: {DEFAULT_K8S_RESOURCE_POLL_INTERVAL_SECONDS})"
        ),
    )
    parser.add_argument(
        "--postgres-recovery-poll-interval-seconds",
        type=positive_seconds,
        default=DEFAULT_POSTGRES_RECOVERY_POLL_INTERVAL_SECONDS,
        help=(
            "seconds between PostgreSQL recovery checks "
            f"(default: {DEFAULT_POSTGRES_RECOVERY_POLL_INTERVAL_SECONDS})"
        ),
    )
    args = parser.parse_args()
    try:
        args.timestamp = parse_timestamp(" ".join(args.date))
    except argparse.ArgumentTypeError as error:
        parser.error(str(error))
    return args


def parse_environment(environment_name: str) -> Env:
    environments = {
        name: env
        for name, env in formatted_tfvars().envs.items()
        if env.kubernetes.enabled
    }
    if not environments:
        raise argparse.ArgumentTypeError(
            "terraform.tfvars.json has no enabled Kubernetes environments"
        )
    if environment_name not in environments:
        available_names = ", ".join(sorted(environments))
        raise argparse.ArgumentTypeError(f"must be one of: {available_names}")
    return environments[environment_name]


def temporary_cluster_name(source_cluster: dict, run_id: str) -> str:
    team_id = source_cluster["spec"]["teamId"]
    source_name = source_cluster["metadata"]["name"]
    name_prefix = source_name
    if name_prefix == "postgres-cluster":
        name_prefix = "pg"
    elif name_prefix.endswith("-postgres-cluster"):
        name_prefix = name_prefix.removesuffix("-postgres-cluster") + "-pg"

    clone_suffix = f"-clone-{run_id[:12]}"
    # Reserve space for the operator's replica Service name.
    max_name_prefix_length = 63 - len("-repl") - len(clone_suffix)
    team_prefix = f"{team_id}-"
    if source_name.startswith(team_prefix) and len(team_id) > max_name_prefix_length:
        raise ValueError(f"teamId {team_id!r} is too long for a temporary clone name")

    name_prefix = name_prefix[:max_name_prefix_length].rstrip("-")
    return f"{name_prefix}{clone_suffix}"


def build_clone(source_cluster: dict, name: str, timestamp: str, run_id: str) -> dict:
    source_spec = source_cluster["spec"]
    volume = source_spec["volume"].copy()
    volume.pop("selector", None)

    spec = {
        "clone": {
            "cluster": source_cluster["metadata"]["name"],
            "uid": source_cluster["metadata"]["uid"],
            "timestamp": timestamp,
        },
        "numberOfInstances": 1,
        "teamId": source_spec["teamId"],
        "postgresql": {"version": source_spec["postgresql"]["version"]},
        "volume": volume,
        "enableMasterLoadBalancer": False,
        "enableMasterPoolerLoadBalancer": False,
        "enableReplicaLoadBalancer": False,
        "enableReplicaPoolerLoadBalancer": False,
    }

    return {
        "apiVersion": source_cluster.get("apiVersion", "acid.zalan.do/v1"),
        "kind": "postgresql",
        "metadata": {
            "name": name,
            "namespace": source_cluster["metadata"]["namespace"],
            "labels": {RUN_ID_LABEL: run_id},
        },
        "spec": spec,
    }


def clone_belongs_to_run(
    k8s: KubernetesPostgresApi,
    namespace: str,
    cluster: str,
    run_id: str,
) -> bool | None:
    try:
        resource = k8s.get_postgresql(namespace, cluster)
    except ApiException as error:
        if error.status == 404:
            return False
        logger.error(f"Could not confirm clone ownership: {error_details(error)}")
        return None
    except (ValueError, OSError) as error:
        logger.error(f"Could not confirm clone ownership: {error}")
        return None
    return resource.get("metadata", {}).get("labels", {}).get(RUN_ID_LABEL) == run_id


def find_source_cluster(
    k8s: KubernetesPostgresApi,
    selector: str,
    namespace: str | None,
) -> dict:
    clusters = k8s.list_postgresql_clusters(namespace)
    matches = [
        cluster
        for cluster in clusters
        if cluster.get("metadata", {}).get("name") == selector
    ]

    if len(matches) == 1:
        return matches[0]
    if not matches:
        scope = f" in namespace {namespace!r}" if namespace else ""
        raise ValueError(f"no PostgreSQL cluster matched {selector!r}{scope}")

    candidates = ", ".join(
        f"{cluster['metadata'].get('namespace', '?')}/"
        f"{cluster['metadata'].get('name', '?')}"
        for cluster in matches
    )
    raise ValueError(
        f"more than one PostgreSQL cluster matched {selector!r}: {candidates}; "
        "pass --namespace to select one"
    )


def wait_for_master(
    k8s: KubernetesApi,
    namespace: str,
    cluster: str,
    poll_interval_seconds: int,
) -> str:
    selector = f"application=spilo,cluster-name={cluster},spilo-role=master"
    while True:
        for pod in k8s.list_resources("pods", namespace, selector):
            ready = any(
                condition.get("type") == "Ready" and condition.get("status") == "True"
                for condition in pod.get("status", {}).get("conditions", [])
            )
            if ready:
                return pod["metadata"]["name"]
        time.sleep(poll_interval_seconds)


def wait_for_recovery(
    k8s: KubernetesApi,
    namespace: str,
    pod: str,
    poll_interval_seconds: int,
) -> None:
    logger.info("Master is ready. Waiting for pg_is_in_recovery() = f...")
    while True:
        result = k8s.exec_in_pod(
            namespace,
            pod,
            [
                "psql",
                "--no-psqlrc",
                "--set",
                "ON_ERROR_STOP=1",
                "--tuples-only",
                "--no-align",
                "--username",
                "postgres",
                "--dbname",
                "postgres",
                "--command",
                "SELECT pg_is_in_recovery();",
            ],
        ).strip()
        if result == "f":
            logger.info("Recovery completed: pg_is_in_recovery() = f.")
            return
        if result != "t":
            raise RuntimeError(f"Unexpected pg_is_in_recovery() result: {result!r}")
        time.sleep(poll_interval_seconds)


def cleanup_clone_storage(
    k8s: KubernetesPostgresApi,
    namespace: str,
    cluster: str,
    poll_interval_seconds: int,
) -> None:
    selector = f"cluster-name={cluster}"
    pvc_deletion_requested = False
    while True:
        stateful_sets = k8s.list_resources("statefulsets", namespace, selector)
        claims = k8s.list_resources("persistentvolumeclaims", namespace, selector)
        if stateful_sets:
            logger.info(
                "Waiting for temporary cluster storage cleanup "
                f"(StatefulSets: {len(stateful_sets)}, PVCs: {len(claims)})..."
            )
            time.sleep(poll_interval_seconds)
            continue

        if not claims:
            return

        if not pvc_deletion_requested:
            logger.info(f"Removing {len(claims)} retained PVC(s) for {cluster}...")
            k8s.delete_persistentvolumeclaims(namespace, selector)
            pvc_deletion_requested = True
        else:
            logger.info(f"Waiting for {len(claims)} retained PVC(s) to be deleted...")
            time.sleep(poll_interval_seconds)


def wait_for_clone_cleanup(
    k8s: KubernetesApi,
    namespace: str,
    cluster: str,
    poll_interval_seconds: int,
) -> None:
    kinds = (
        "pods,statefulsets,services,endpoints,endpointslices,configmaps,secrets,"
        "jobs,deployments,replicasets,persistentvolumeclaims"
    )
    while True:
        resources = []
        for kind in kinds.split(","):
            resources.extend(
                k8s.list_resources(kind, namespace, f"cluster-name={cluster}")
            )
        if not resources:
            logger.info("Temporary cluster cleanup completed.")
            return
        remaining = ", ".join(
            f"{resource['kind']}/{resource['metadata']['name']}"
            for resource in resources
        )
        logger.info(f"Waiting for deletion: {remaining}...")
        time.sleep(poll_interval_seconds)


def run_check(args: argparse.Namespace, k8s: KubernetesPostgresApi) -> int:
    k8s_resource_poll_interval_seconds = getattr(
        args,
        "k8s_resource_poll_interval_seconds",
        DEFAULT_K8S_RESOURCE_POLL_INTERVAL_SECONDS,
    )
    recovery_poll_interval_seconds = getattr(
        args,
        "postgres_recovery_poll_interval_seconds",
        DEFAULT_POSTGRES_RECOVERY_POLL_INTERVAL_SECONDS,
    )
    source = find_source_cluster(k8s, args.postgres, args.namespace)
    database = args.database
    run_id = uuid.uuid4().hex
    clone_name = temporary_cluster_name(source, run_id)
    clone = build_clone(source, clone_name, args.timestamp, run_id)
    namespace = source["metadata"]["namespace"]

    logger.info(
        f"Restoring {args.postgres} at {args.timestamp} "
        f"into temporary cluster {clone_name} in namespace {namespace}..."
    )
    created = False
    creation_attempted = False
    try:
        creation_attempted = True
        k8s.create_postgresql(namespace, clone)
        created = True
        pod = wait_for_master(
            k8s, namespace, clone_name, k8s_resource_poll_interval_seconds
        )
        wait_for_recovery(k8s, namespace, pod, recovery_poll_interval_seconds)
        logger.info(f"Restore ready. Running SQL in database {database}...")
        result = k8s.exec_in_pod(
            namespace,
            pod,
            [
                "psql",
                "--no-psqlrc",
                "--set",
                "ON_ERROR_STOP=1",
                "--pset",
                "pager=off",
                "--username",
                "postgres",
                "--dbname",
                database,
                "--command",
                args.query,
            ],
        )
        logger.info(f"SQL result:\n{result.rstrip()}")
        logger.info("SQL completed successfully.")
    finally:
        operation_failed = sys.exc_info()[0] is not None
        should_delete = created

        if creation_attempted and not created:
            ownership = clone_belongs_to_run(
                k8s,
                namespace,
                clone_name,
                run_id,
            )
            if ownership is None:
                detail = f"could not confirm ownership of {namespace}/{clone_name}"
                logger.error(detail)
                if not operation_failed:
                    raise RuntimeError(detail)
            else:
                should_delete = ownership

        if should_delete:
            logger.info(f"Removing temporary cluster {clone_name}...")
            try:
                k8s.delete_postgresqls(
                    namespace,
                    f"{RUN_ID_LABEL}={run_id}",
                )
                logger.info("Waiting for temporary PostgreSQL resource deletion...")
                while True:
                    try:
                        k8s.get_postgresql(namespace, clone_name)
                    except ApiException as error:
                        if error.status == 404:
                            break
                        raise
                    time.sleep(k8s_resource_poll_interval_seconds)
                cleanup_clone_storage(
                    k8s, namespace, clone_name, k8s_resource_poll_interval_seconds
                )
                wait_for_clone_cleanup(
                    k8s, namespace, clone_name, k8s_resource_poll_interval_seconds
                )
            except Exception as error:
                logger.error(
                    f"Cleanup failed for {namespace}/{clone_name}: "
                    f"{error_details(error)}"
                )
                if not operation_failed:
                    raise

    logger.info(
        "SUCCESS: backup restored, SQL completed, temporary cluster resources removed.",
    )
    return 0


def main() -> int:
    try:
        args = parse_args()
        environment = args.environment
        logger.info(f"Using Kubernetes environment {environment.short_name}...")
        k8s = KubernetesPostgresApi(environment)
        return run_check(args, k8s)
    except Exception as error:
        logger.error(f"FAILED: backup restore check: {error_details(error)}")
        return 1
    except KeyboardInterrupt:
        logger.error(
            "FAILED: backup restore check interrupted; cleanup may be incomplete."
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
