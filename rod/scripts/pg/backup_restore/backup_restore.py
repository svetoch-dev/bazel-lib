"""Restore a PostgreSQL backup into a temporary cluster and run a query."""

import argparse
import re
import sys
import time
import uuid
from datetime import datetime

from kubernetes import client, stream
from kubernetes.client.exceptions import ApiException

from rod.libs.py.k8s.client import k8s_client_get
from rod.libs.py.tf.tfvars import Env, formatted_tfvars


RUN_ID_LABEL = "backup-restore-run-id"
POSTGRES_GROUP = "acid.zalan.do"
POSTGRES_VERSION = "v1"
POSTGRES_PLURAL = "postgresqls"
K8S_RESOURCE_POLL_INTERVAL_SECONDS = 5
POSTGRES_RECOVERY_POLL_INTERVAL_SECONDS = 3
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
        help="source cluster name or Postgres teamId (for example: example-team)",
    )
    parser.add_argument(
        "--namespace",
        help="limit source cluster lookup and create the clone in this namespace",
    )
    parser.add_argument(
        "--environment",
        help=(
            "environment key or unique short name from terraform.tfvars.json; "
            "inferred when only one Kubernetes environment is enabled"
        ),
    )
    parser.add_argument(
        "--database",
        help="database for the query (inferred from the source cluster when omitted)",
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
    args = parser.parse_args()
    try:
        args.timestamp = parse_timestamp(" ".join(args.date))
    except argparse.ArgumentTypeError as error:
        parser.error(str(error))
    return args


def find_environment(environment_name: str | None) -> Env:
    environments = {
        name: env
        for name, env in formatted_tfvars().envs.items()
        if env.kubernetes.enabled
    }
    environment_names = ", ".join(sorted(environments)) or "none"

    if environment_name is not None:
        if environment_name in environments:
            return environments[environment_name]

        matching_names = [
            name
            for name, env in environments.items()
            if env.short_name == environment_name
        ]
        if len(matching_names) == 1:
            return environments[matching_names[0]]
        if matching_names:
            names = ", ".join(sorted(matching_names))
            raise ValueError(
                f"environment short name {environment_name!r} is ambiguous; "
                f"use its terraform.tfvars.json key: {names}"
            )
        raise ValueError(
            f"no Kubernetes environment matched {environment_name!r}; "
            f"available environments: {environment_names}"
        )

    if len(environments) == 1:
        return next(iter(environments.values()))
    if not environments:
        raise ValueError("terraform.tfvars.json has no enabled Kubernetes environments")

    raise ValueError(
        "more than one Kubernetes environment is enabled; pass --environment "
        f"with one of: {environment_names}"
    )


class PodCommandError(RuntimeError):
    def __init__(
        self,
        namespace: str,
        pod: str,
        command: list[str],
        return_code: int,
        stdout: str,
        stderr: str,
    ):
        self.namespace = namespace
        self.pod = pod
        self.command = command
        self.return_code = return_code
        self.stdout = stdout
        self.stderr = stderr
        message = (
            f"Command {command[0]!r} in pod {namespace}/{pod} "
            f"exited with code {return_code}"
        )
        if stderr.strip():
            message += f"\nstderr:\n{stderr.strip()}"
        if stdout.strip():
            message += f"\nstdout before failure:\n{stdout.strip()}"
        super().__init__(message)


class KubernetesApi:
    """Small adapter around the Kubernetes Python client used by this script."""

    def __init__(self, environment: Env):
        self.api = k8s_client_get(environment, use_exec=True)
        # Exec uses WebSockets and changes the API client's request protocol.
        self.exec_core = k8s_client_get(environment, use_exec=True).v1

    def list_postgresql_clusters(self, namespace: str | None) -> list[dict]:
        if namespace:
            result = self.api.list_namespaced_custom_object(
                POSTGRES_GROUP, POSTGRES_VERSION, namespace, POSTGRES_PLURAL
            )
        else:
            result = self.api.list_cluster_custom_object(
                POSTGRES_GROUP, POSTGRES_VERSION, POSTGRES_PLURAL
            )
        return result["items"]

    def get_postgresql(self, namespace: str, name: str) -> dict:
        return self.api.get_namespaced_custom_object(
            POSTGRES_GROUP,
            POSTGRES_VERSION,
            namespace,
            POSTGRES_PLURAL,
            name,
        )

    def create_postgresql(self, namespace: str, resource: dict) -> None:
        self.api.create_namespaced_custom_object(
            POSTGRES_GROUP,
            POSTGRES_VERSION,
            namespace,
            POSTGRES_PLURAL,
            resource,
        )

    def delete_postgresqls(self, namespace: str, selector: str) -> None:
        self.api.delete_collection_namespaced_custom_object(
            POSTGRES_GROUP,
            POSTGRES_VERSION,
            namespace,
            POSTGRES_PLURAL,
            label_selector=selector,
        )

    def list_resources(self, kind: str, namespace: str, selector: str) -> list[dict]:
        list_methods = {
            "pods": self.api.list_namespaced_pod,
            "statefulsets": self.api.list_namespaced_stateful_set,
            "services": self.api.list_namespaced_service,
            "endpoints": self.api.list_namespaced_endpoints,
            "endpointslices": self.api.list_namespaced_endpoint_slice,
            "configmaps": self.api.list_namespaced_config_map,
            "secrets": self.api.list_namespaced_secret,
            "jobs": self.api.list_namespaced_job,
            "deployments": self.api.list_namespaced_deployment,
            "replicasets": self.api.list_namespaced_replica_set,
            "persistentvolumeclaims": self.api.list_namespaced_persistent_volume_claim,
        }
        result = list_methods[kind](namespace, label_selector=selector)
        resources = [resource.to_dict() for resource in result.items]
        for resource in resources:
            resource["kind"] = kind
        return resources

    def delete_persistentvolumeclaims(self, namespace: str, selector: str) -> None:
        self.api.delete_collection_namespaced_persistent_volume_claim(
            namespace,
            label_selector=selector,
            body=client.V1DeleteOptions(),
        )

    def exec_in_pod(self, namespace: str, pod: str, command: list[str]) -> str:
        response = stream.stream(
            self.exec_core.connect_get_namespaced_pod_exec,
            pod,
            namespace,
            command=command,
            container="postgres",
            stderr=True,
            stdin=False,
            stdout=True,
            tty=False,
            _preload_content=False,
        )
        try:
            response.run_forever()
            stdout = response.read_stdout()
            stderr = response.read_stderr()
            return_code = response.returncode
        finally:
            response.close()

        if return_code is None:
            raise RuntimeError(f"Pod command did not return an exit code: {pod}")
        if return_code != 0:
            raise PodCommandError(
                namespace,
                pod,
                command,
                return_code,
                stdout,
                stderr,
            )
        return stdout


def error_details(error: Exception) -> str:
    if isinstance(error, ApiException):
        details = f"Kubernetes API returned {error.status}: {error.reason}"
        if error.body:
            details += f"\n{error.body}"
        return details
    return str(error)


def temporary_cluster_name(source_cluster: dict, run_id: str) -> str:
    team_id = source_cluster["spec"]["teamId"]
    source_name = source_cluster["metadata"]["name"]
    cluster_name = source_name.removeprefix(f"{team_id}-")
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789-"
    cluster_name = "".join(
        char if char in allowed else "-" for char in cluster_name.lower()
    )
    cluster_name = cluster_name.removesuffix("-cluster")
    if cluster_name == "cluster":
        cluster_name = ""
    elif cluster_name == "postgres":
        cluster_name = "pg"
    elif cluster_name.endswith("-postgres"):
        cluster_name = cluster_name.removesuffix("-postgres") + "-pg"

    suffix = f"-clone-{run_id[:12]}"
    # Reserve space for the operator's replica Service name.
    max_prefix_length = 63 - len("-repl") - len(suffix)
    if len(team_id) > max_prefix_length:
        raise ValueError(f"teamId {team_id!r} is too long for a temporary clone name")

    available_length = max(0, max_prefix_length - len(team_id) - 1)
    cluster_name = cluster_name[:available_length].strip("-")
    prefix = f"{team_id}-{cluster_name}" if cluster_name else team_id
    return f"{prefix}{suffix}"


def build_clone(source_cluster: dict, name: str, timestamp: str, run_id: str) -> dict:
    source_spec = source_cluster["spec"]
    source_volume = source_spec["volume"]
    volume = {}
    for field in ("size", "storageClass"):
        if field in source_volume:
            volume[field] = source_volume[field]

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
    k8s: KubernetesApi,
    namespace: str,
    cluster: str,
    run_id: str,
) -> bool | None:
    try:
        resource = k8s.get_postgresql(namespace, cluster)
    except ApiException as error:
        if error.status == 404:
            return False
        print(
            f"could not confirm clone ownership: {error_details(error)}",
            file=sys.stderr,
        )
        return None
    except (ValueError, OSError) as error:
        print(f"could not confirm clone ownership: {error}", file=sys.stderr)
        return None
    return resource.get("metadata", {}).get("labels", {}).get(RUN_ID_LABEL) == run_id


def find_source_cluster(
    k8s: KubernetesApi,
    selector: str,
    namespace: str | None,
) -> dict:
    clusters = k8s.list_postgresql_clusters(namespace)

    exact_name_matches = [
        cluster
        for cluster in clusters
        if cluster.get("metadata", {}).get("name") == selector
    ]
    if exact_name_matches:
        matches = exact_name_matches
    else:
        team_matches = [
            cluster
            for cluster in clusters
            if cluster.get("spec", {}).get("teamId") == selector
        ]
        namespace_matches = [
            cluster
            for cluster in clusters
            if cluster.get("metadata", {}).get("namespace") == selector
        ]
        matches = team_matches or namespace_matches

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


def resolve_database(source_cluster: dict, selector: str, requested: str | None) -> str:
    if requested:
        return requested

    spec = source_cluster.get("spec", {})
    configured_databases = list((spec.get("databases") or {}).keys())
    for database in spec.get("preparedDatabases") or {}:
        if database not in configured_databases:
            configured_databases.append(database)
    if selector in configured_databases:
        return selector
    if len(configured_databases) == 1:
        return configured_databases[0]
    if not configured_databases:
        return "postgres"
    raise ValueError(
        "could not infer the query database; pass --database. Configured "
        f"databases: {', '.join(configured_databases)}"
    )


def wait_for_master(k8s: KubernetesApi, namespace: str, cluster: str) -> str:
    selector = f"application=spilo,cluster-name={cluster},spilo-role=master"
    while True:
        for pod in k8s.list_resources("pods", namespace, selector):
            ready = any(
                condition.get("type") == "Ready" and condition.get("status") == "True"
                for condition in pod.get("status", {}).get("conditions", [])
            )
            if ready:
                return pod["metadata"]["name"]
        time.sleep(K8S_RESOURCE_POLL_INTERVAL_SECONDS)


def wait_for_recovery(k8s: KubernetesApi, namespace: str, pod: str) -> None:
    print("Master is ready. Waiting for pg_is_in_recovery() = f...", file=sys.stderr)
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
            print("Recovery completed: pg_is_in_recovery() = f.", file=sys.stderr)
            return
        if result != "t":
            raise RuntimeError(f"Unexpected pg_is_in_recovery() result: {result!r}")
        time.sleep(POSTGRES_RECOVERY_POLL_INTERVAL_SECONDS)


def cleanup_clone_storage(k8s: KubernetesApi, namespace: str, cluster: str) -> None:
    selector = f"cluster-name={cluster}"
    pvc_deletion_requested = False
    while True:
        stateful_sets = k8s.list_resources("statefulsets", namespace, selector)
        claims = k8s.list_resources("persistentvolumeclaims", namespace, selector)
        if stateful_sets:
            print(
                "Waiting for temporary cluster storage cleanup "
                f"(StatefulSets: {len(stateful_sets)}, PVCs: {len(claims)})...",
                file=sys.stderr,
            )
            time.sleep(K8S_RESOURCE_POLL_INTERVAL_SECONDS)
            continue

        if not claims:
            return

        if not pvc_deletion_requested:
            print(
                f"Removing {len(claims)} retained PVC(s) for {cluster}...",
                file=sys.stderr,
            )
            k8s.delete_persistentvolumeclaims(namespace, selector)
            pvc_deletion_requested = True
        else:
            print(
                f"Waiting for {len(claims)} retained PVC(s) to be deleted...",
                file=sys.stderr,
            )
            time.sleep(K8S_RESOURCE_POLL_INTERVAL_SECONDS)


def wait_for_clone_cleanup(k8s: KubernetesApi, namespace: str, cluster: str) -> None:
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
            print("Temporary cluster cleanup completed.", file=sys.stderr)
            return
        remaining = ", ".join(
            f"{resource['kind']}/{resource['metadata']['name']}"
            for resource in resources
        )
        print(f"Waiting for deletion: {remaining}...", file=sys.stderr)
        time.sleep(K8S_RESOURCE_POLL_INTERVAL_SECONDS)


def run_check(args: argparse.Namespace, k8s: KubernetesApi) -> int:
    source = find_source_cluster(k8s, args.postgres, args.namespace)
    database = resolve_database(source, args.postgres, args.database)
    run_id = uuid.uuid4().hex
    clone_name = temporary_cluster_name(source, run_id)
    clone = build_clone(source, clone_name, args.timestamp, run_id)
    namespace = source["metadata"]["namespace"]

    print(
        f"Restoring {args.postgres} at {args.timestamp} "
        f"into temporary cluster {clone_name} in namespace {namespace}...",
        file=sys.stderr,
    )
    created = False
    creation_attempted = False
    try:
        creation_attempted = True
        k8s.create_postgresql(namespace, clone)
        created = True
        pod = wait_for_master(k8s, namespace, clone_name)
        wait_for_recovery(k8s, namespace, pod)
        print(f"Restore ready. Running SQL in database {database}...", file=sys.stderr)
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
        print("SQL result:", flush=True)
        print(result, end="", flush=True)
        print("SQL completed successfully.", file=sys.stderr)
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
                print(detail, file=sys.stderr)
                if not operation_failed:
                    raise RuntimeError(detail)
            else:
                should_delete = ownership

        if should_delete:
            print(f"Removing temporary cluster {clone_name}...", file=sys.stderr)
            try:
                k8s.delete_postgresqls(
                    namespace,
                    f"{RUN_ID_LABEL}={run_id}",
                )
                print(
                    "Waiting for temporary PostgreSQL resource deletion...",
                    file=sys.stderr,
                )
                while True:
                    try:
                        k8s.get_postgresql(namespace, clone_name)
                    except ApiException as error:
                        if error.status == 404:
                            break
                        raise
                    time.sleep(K8S_RESOURCE_POLL_INTERVAL_SECONDS)
                cleanup_clone_storage(k8s, namespace, clone_name)
                wait_for_clone_cleanup(k8s, namespace, clone_name)
            except Exception as error:
                print(
                    f"Cleanup failed for {namespace}/{clone_name}: "
                    f"{error_details(error)}",
                    file=sys.stderr,
                )
                if not operation_failed:
                    raise

    print(
        "SUCCESS: backup restored, SQL completed, temporary cluster resources removed.",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    args = parse_args()
    try:
        environment = find_environment(args.environment)
        print(
            f"Using Kubernetes environment {environment.short_name}...",
            file=sys.stderr,
        )
        k8s = KubernetesApi(environment)
        return run_check(args, k8s)
    except Exception as error:
        print(
            f"FAILED: backup restore check: {error_details(error)}",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print(
            "FAILED: backup restore check interrupted; cleanup may be incomplete.",
            file=sys.stderr,
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
