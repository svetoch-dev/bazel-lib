"""Restore a PostgreSQL backup into a temporary cluster and run a query."""

import argparse
import re
import time
import uuid
from datetime import datetime

from kubernetes.client.exceptions import ApiException

from rod.libs.py.k8s.api import KubernetesApi, get_error_details
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
    """Parse a positive integer for a polling interval.

    Args:
        value: Command line value in seconds.

    Returns:
        A whole number greater than zero.

    Raises:
        argparse.ArgumentTypeError: The value is not a positive integer.
    """
    try:
        seconds = int(value)
    except ValueError:
        seconds = None

    if seconds is None or seconds <= 0:
        raise argparse.ArgumentTypeError("must be a positive whole number of seconds")

    return seconds


def parse_timestamp(value: str) -> str:
    """Normalize the recovery target while preserving fractional seconds.

    Args:
        value: Date and time with hyphens or dots in the date. Missing timezone
            means UTC; explicit offsets and Z are accepted.

    Returns:
        Timestamp with a T separator and an explicit timezone offset.

    Raises:
        argparse.ArgumentTypeError: The format or date is invalid.
    """
    timestamp = " ".join(value.split())
    match = ISO_TIMESTAMP_PATTERN.fullmatch(timestamp)
    if match is None:
        raise argparse.ArgumentTypeError(TIMESTAMP_FORMAT_ERROR)

    date, time, fraction, offset = match.group("date", "time", "fraction", "offset")
    date = date.replace(".", "-")
    fraction = fraction or ""
    if not offset or offset.lower() == "z":
        offset = "+00:00"

    try:
        # Validate microseconds; return the full fractional part below.
        datetime.fromisoformat(f"{date}T{time}{fraction[:7]}{offset}")
    except ValueError as error:
        raise argparse.ArgumentTypeError(TIMESTAMP_FORMAT_ERROR) from error

    return f"{date}T{time}{fraction}{offset}"


def parse_args() -> argparse.Namespace:
    """Read and validate command line arguments.

    Returns:
        Parsed arguments with the environment object and normalized timestamp.
    """
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
    """Select an enabled Kubernetes environment from terraform.tfvars.json.

    Args:
        environment_name: Exact key in the tfvars envs mapping.

    Returns:
        Environment settings for connecting to Kubernetes.

    Raises:
        argparse.ArgumentTypeError: No enabled environment matches the key.
    """
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
    """Append a short clone suffix and shorten the source name if needed.

    Args:
        source_cluster: Source PostgreSQL resource, including metadata.name.
        run_id: Full run ID; only its first four characters enter the name.

    Returns:
        Clone name with room for the operator's -repl Service suffix.
    """
    source_name = source_cluster["metadata"]["name"]
    clone_suffix = f"-clone-{run_id[:4]}"
    # Kubernetes names are limited to 63 characters; reserve room for "-repl".
    max_name_prefix_length = 63 - len("-repl") - len(clone_suffix)

    name_prefix = source_name[:max_name_prefix_length].rstrip("-")
    return f"{name_prefix}{clone_suffix}"


def build_clone(source_cluster: dict, name: str, timestamp: str, run_id: str) -> dict:
    """Build a temporary PostgreSQL resource for point-in-time recovery.

    Args:
        source_cluster: Source PostgreSQL resource with its UID and settings.
        name: Temporary clone name.
        timestamp: Normalized recovery target with an explicit timezone.
        run_id: Full run ID used to identify this run's resource during cleanup.

    Returns:
        Clone manifest with one instance and external load balancers disabled.
    """
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
    """Check whether a PostgreSQL resource carries this run's ownership label.

    Args:
        k8s: PostgreSQL API wrapper.
        namespace: Namespace containing the clone.
        cluster: Temporary PostgreSQL resource name.
        run_id: Full run ID expected in the ownership label.

    Returns:
        True if owned by this run, False if absent or owned by another run,
        or None if ownership could not be checked.
    """
    try:
        resource = k8s.get_postgresql(namespace, cluster)
    except ApiException as error:
        if error.status == 404:
            return False
        logger.error(f"Could not confirm clone ownership: {get_error_details(error)}")
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
    """Find exactly one PostgreSQL resource by name.

    Args:
        k8s: PostgreSQL API wrapper.
        selector: Exact source resource name.
        namespace: Namespace to search, or None to search all namespaces.

    Returns:
        Matching PostgreSQL resource.

    Raises:
        ValueError: No resource matches, or the name exists in several namespaces.
    """
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
    """Wait until a master Pod has a Ready condition, without a timeout.

    Args:
        k8s: Kubernetes API wrapper.
        namespace: Namespace containing the clone.
        cluster: Temporary PostgreSQL resource name used in Pod labels.
        poll_interval_seconds: Delay between readiness checks.

    Returns:
        Name of a Ready master Pod.
    """
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
    """Wait for pg_is_in_recovery() to return false, without a timeout.

    Args:
        k8s: Kubernetes API wrapper.
        namespace: Namespace containing the Pod.
        pod: Ready master Pod name.
        poll_interval_seconds: Delay between recovery checks.

    Raises:
        RuntimeError: The recovery probe returns neither t nor f.
    """
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
    """Wait for StatefulSets to disappear, then delete retained PVCs.

    Args:
        k8s: PostgreSQL API wrapper.
        namespace: Namespace containing the clone's storage.
        cluster: Temporary cluster name used in resource labels.
        poll_interval_seconds: Delay between storage checks.
    """
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
    """Wait for supported resources labelled with the clone name to disappear.

    Args:
        k8s: Kubernetes API wrapper.
        namespace: Namespace containing the clone's resources.
        cluster: Temporary cluster name used in resource labels.
        poll_interval_seconds: Delay between resource checks.
    """
    resource_types = (
        "pods",
        "statefulsets",
        "services",
        "endpoints",
        "endpointslices",
        "configmaps",
        "secrets",
        "jobs",
        "deployments",
        "replicasets",
        "persistentvolumeclaims",
    )
    while True:
        resources = []
        for kind in resource_types:
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
    """Restore a backup, run SQL, and clean up this run's temporary resources.

    Args:
        args: Validated arguments returned by parse_args().
        k8s: PostgreSQL API wrapper for the selected environment.

    Returns:
        Zero after SQL and cleanup complete successfully.

    Raises:
        Exception: Source lookup, restoration, SQL, or cleanup fails.
    """
    k8s_resource_poll_interval_seconds = args.k8s_resource_poll_interval_seconds
    recovery_poll_interval_seconds = args.postgres_recovery_poll_interval_seconds
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
    operation_failed = False
    try:
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
    except BaseException:
        operation_failed = True
        raise
    finally:
        should_delete = created

        if not created:
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
                    f"{get_error_details(error)}"
                )
                if not operation_failed:
                    raise

    logger.info(
        "SUCCESS: backup restored, SQL completed, temporary cluster resources removed.",
    )
    return 0


def main() -> int:
    """Connect to Kubernetes and run the backup check.

    Returns:
        Zero on success, one on runtime failure, or 130 on interruption.
        Argument errors exit through argparse before a return value is produced.
    """
    try:
        args = parse_args()
        environment = args.environment
        logger.info(f"Using Kubernetes environment {environment.short_name}...")
        k8s = KubernetesPostgresApi(environment)
        return run_check(args, k8s)
    except Exception as error:
        logger.error(f"FAILED: backup restore check: {get_error_details(error)}")
        return 1
    except KeyboardInterrupt:
        logger.error(
            "FAILED: backup restore check interrupted; cleanup may be incomplete."
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
