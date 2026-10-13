"""Restore a PostgreSQL backup into a temporary cluster and run a query."""

import argparse
import json
import re
import subprocess
import sys
import time
import uuid
from datetime import datetime


RUN_ID_LABEL = "backup-restore-run-id"
K8S_POLL_INTERVAL = 5
RECOVERY_POLL_INTERVAL = 3
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


def kubectl(args: list[str], *, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["kubectl", *args],
        input=input_text,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def list_resources(kind: str, namespace: str, selector: str) -> list[dict]:
    output = kubectl(
        [
            "get",
            kind,
            "--namespace",
            namespace,
            "--selector",
            selector,
            "-o",
            "json",
        ]
    )
    return json.loads(output)["items"]


def command_error(error: subprocess.CalledProcessError) -> str:
    details = (error.stderr or "").strip() or str(error)
    if error.stdout and error.stdout.strip():
        details += f"\nOutput before failure:\n{error.stdout.strip()}"
    return f"Command exited with code {error.returncode}: {details}"


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
    namespace: str,
    cluster: str,
    run_id: str,
) -> bool | None:
    try:
        output = kubectl(
            [
                "get",
                "postgresql",
                cluster,
                "--namespace",
                namespace,
                "-o",
                "json",
            ]
        )
        resource = json.loads(output)
    except subprocess.CalledProcessError as error:
        if "NotFound" in (error.stderr or ""):
            return False
        print(
            f"could not confirm clone ownership: {command_error(error)}",
            file=sys.stderr,
        )
        return None
    except (ValueError, OSError) as error:
        print(f"could not confirm clone ownership: {error}", file=sys.stderr)
        return None
    return resource.get("metadata", {}).get("labels", {}).get(RUN_ID_LABEL) == run_id


def find_source_cluster(
    selector: str,
    namespace: str | None,
) -> dict:
    command = ["get", "postgresql"]
    if namespace:
        command.extend(["--namespace", namespace])
    else:
        command.append("--all-namespaces")
    command.extend(["-o", "json"])
    output = kubectl(command)
    clusters = json.loads(output)["items"]

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


def wait_for_master(namespace: str, cluster: str) -> str:
    selector = f"application=spilo,cluster-name={cluster},spilo-role=master"
    while True:
        for pod in list_resources("pods", namespace, selector):
            ready = any(
                condition.get("type") == "Ready" and condition.get("status") == "True"
                for condition in pod.get("status", {}).get("conditions", [])
            )
            if ready:
                return pod["metadata"]["name"]
        time.sleep(K8S_POLL_INTERVAL)


def wait_for_recovery(namespace: str, pod: str) -> None:
    print("Master is ready. Waiting for pg_is_in_recovery() = f...", file=sys.stderr)
    while True:
        result = kubectl(
            [
                "exec",
                "--namespace",
                namespace,
                pod,
                "--container",
                "postgres",
                "--",
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
            ]
        ).strip()
        if result == "f":
            print("Recovery completed: pg_is_in_recovery() = f.", file=sys.stderr)
            return
        if result != "t":
            raise RuntimeError(f"Unexpected pg_is_in_recovery() result: {result!r}")
        time.sleep(RECOVERY_POLL_INTERVAL)


def cleanup_clone_storage(namespace: str, cluster: str) -> None:
    selector = f"cluster-name={cluster}"
    while True:
        stateful_sets = list_resources("statefulsets", namespace, selector)
        claims = list_resources("persistentvolumeclaims", namespace, selector)
        if stateful_sets:
            print(
                "Waiting for temporary cluster storage cleanup "
                f"(StatefulSets: {len(stateful_sets)}, PVCs: {len(claims)})...",
                file=sys.stderr,
            )
            time.sleep(K8S_POLL_INTERVAL)
            continue

        if not claims:
            return

        print(
            f"Removing {len(claims)} retained PVC(s) for {cluster}...",
            file=sys.stderr,
        )
        kubectl(
            [
                "delete",
                "persistentvolumeclaims",
                "--namespace",
                namespace,
                "--selector",
                selector,
                "--ignore-not-found=true",
                "--wait=true",
            ]
        )


def wait_for_clone_cleanup(namespace: str, cluster: str) -> None:
    kinds = (
        "pods,statefulsets,services,endpoints,endpointslices,configmaps,secrets,"
        "jobs,deployments,replicasets,persistentvolumeclaims"
    )
    while True:
        resources = list_resources(kinds, namespace, f"cluster-name={cluster}")
        if not resources:
            print("Temporary cluster cleanup completed.", file=sys.stderr)
            return
        remaining = ", ".join(
            f"{resource['kind']}/{resource['metadata']['name']}"
            for resource in resources
        )
        print(f"Waiting for deletion: {remaining}...", file=sys.stderr)
        time.sleep(K8S_POLL_INTERVAL)


def run_check(args: argparse.Namespace) -> int:
    source = find_source_cluster(args.postgres, args.namespace)
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
        kubectl(
            ["create", "-f", "-"],
            input_text=json.dumps(clone),
        )
        created = True
        pod = wait_for_master(namespace, clone_name)
        wait_for_recovery(namespace, pod)
        print(f"Restore ready. Running SQL in database {database}...", file=sys.stderr)
        result = kubectl(
            [
                "exec",
                "--namespace",
                namespace,
                pod,
                "--container",
                "postgres",
                "--",
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
            ]
        )
        print("SQL result:", flush=True)
        print(result, end="", flush=True)
        print("SQL completed successfully.", file=sys.stderr)
    finally:
        operation_failed = sys.exc_info()[0] is not None
        should_delete = created

        if creation_attempted and not created:
            ownership = clone_belongs_to_run(
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
                kubectl(
                    [
                        "delete",
                        "postgresql",
                        "--selector",
                        f"{RUN_ID_LABEL}={run_id}",
                        "--namespace",
                        namespace,
                        "--ignore-not-found=true",
                        "--wait=true",
                    ]
                )
                cleanup_clone_storage(namespace, clone_name)
                wait_for_clone_cleanup(namespace, clone_name)
            except (subprocess.CalledProcessError, ValueError, OSError) as error:
                detail = (
                    command_error(error)
                    if isinstance(error, subprocess.CalledProcessError)
                    else str(error)
                )
                print(
                    f"Cleanup failed for {namespace}/{clone_name}: {detail}",
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
        return run_check(args)
    except (
        subprocess.CalledProcessError,
        RuntimeError,
        KeyError,
        ValueError,
        OSError,
    ) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print(
                f"FAILED: backup restore check: {command_error(error)}",
                file=sys.stderr,
            )
        else:
            print(f"FAILED: backup restore check: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print(
            "FAILED: backup restore check interrupted; cleanup may be incomplete.",
            file=sys.stderr,
        )
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
