# PostgreSQL backup restore check

The `backup_restore` command verifies a point-in-time backup by asking the
Zalando Postgres Operator to restore a physical base backup and replay archived
WAL up to the requested recovery target, running a SQL query on the restored
cluster, and deleting the temporary cluster.

Spilo performs the restoration. Support for WAL-E or WAL-G depends on the
installed Spilo image and its restore configuration; this command does not
select the tool. Logical backups produced by `pg_dump` are not checked.

## Prerequisites

- The calling repository must depend on a revision of `svetoch_bazel_lib` that
  contains this target. Update its dependency pin and keep any resulting changes
  to `MODULE.bazel.lock`. No additional Bazel target or Helm manifest is needed.
- The caller's workspace must contain `terraform.tfvars.json` with the target
  environment. If exactly one Kubernetes environment is enabled, it is selected
  automatically; otherwise pass `--environment` with its key or unique short
  name. The shared client currently supports GCP and YC environments.
- Cloud credentials and the provider's exec authenticator must be available:
  Google Application Default Credentials and `gke-gcloud-auth-plugin` for GCP,
  or YC credentials and the `yc` CLI for YC. The client connects directly to
  the Kubernetes API and does not require an active kubeconfig context or the
  `kubectl` executable. Exec authentication refreshes credentials during long
  restore checks.
- The Kubernetes user needs `get`, `list`, `create`, `delete`, and
  `deletecollection` on `postgresql` resources; `list` on Pods, StatefulSets,
  PVCs, Services, Endpoints, EndpointSlices, ConfigMaps, Secrets, Jobs,
  Deployments, and ReplicaSets; `create` on `pods/exec`; and `delete` plus
  `deletecollection` on PVCs in the selected namespace.
- The operator and Spilo must already support restoration from the source
  cluster's physical backup storage. The temporary Pod needs storage access and
  credentials. Local cloud credentials alone do not grant access to the Pod.
  A base backup before the requested recovery target and the archived WAL needed
  to reach that target must be available.
- The Kubernetes cluster needs capacity for one additional PostgreSQL Pod and
  a PVC with the source cluster's volume size and storage class.

## Usage

Run it from a repository that depends on `svetoch_bazel_lib`:

```sh
bazel run @svetoch_bazel_lib//rod/scripts/pg/backup_restore -- \
  --environment YOUR_ENVIRONMENT \
  --postgres example-team \
  --date '2024.01.07 00:00:00' \
  --k8s-resource-poll-interval-seconds 5 \
  --postgres-recovery-poll-interval-seconds 3 \
  --query 'SELECT count(1) FROM example_table'
```

The polling options are optional. Kubernetes resource readiness and cleanup
checks use `--k8s-resource-poll-interval-seconds` (default: 5 seconds);
PostgreSQL recovery checks
use `--postgres-recovery-poll-interval-seconds` (default: 3 seconds). Both
values must be positive whole numbers of seconds.

Replace `YOUR_ENVIRONMENT` with an environment key or unique short name from
`terraform.tfvars.json`. You can omit `--environment` when exactly one enabled
Kubernetes environment is configured.

`--postgres` can be a Kubernetes cluster name or a Postgres Operator `teamId`.
For example, `example-team` resolves to the cluster whose team ID is
`example-team`. If multiple clusters match, pass `--namespace` to narrow the
lookup. Without `--namespace`, the command searches all namespaces in the
selected environment, so its Kubernetes identity must be allowed to list
PostgreSQL resources across namespaces.

The database is inferred from the source cluster: the value passed to
`--postgres` if it is a configured database, or the only configured database.
For clusters with several databases, pass `--database`. Timestamps without a
timezone are interpreted as UTC; ISO timestamps with an explicit offset are
also accepted. The temporary clone uses the
source cluster's PostgreSQL version, volume size, and storage class, with one
instance. Custom PostgreSQL parameters and other optional source cluster
settings are not carried over to the clone.

Temporary names use the resolved source cluster name and preserve its full
`teamId` prefix. Only the remaining name portion is shortened: a trailing
`-postgres-cluster` becomes `-pg-clone-<run_id>`, for example:
`example-team-postgres-cluster` becomes
`example-team-pg-clone-<run_id>`. Long names are shortened to leave room for
operator-generated replica Service names, while keeping `teamId` intact. If the
team ID alone leaves insufficient room for the clone suffix, the command fails
before creating the clone.

The command waits for a Ready master Pod, then polls `pg_is_in_recovery()` in
the `postgres` database until it returns `false`. The intervals are controlled
by `--k8s-resource-poll-interval-seconds` and
`--postgres-recovery-poll-interval-seconds`. Only then does it run the user's
query and remove the temporary cluster. A failed SQL probe or an unexpected
result fails the check and triggers cleanup. It has no built-in timeout;
readiness and recovery waits can continue indefinitely.

SQL results include column headings. The command waits for the PostgreSQL
resource to be deleted, removes retained PVCs, and waits for the listed resource
types carrying the temporary clone's `cluster-name` label to disappear.
Unlabelled resources and cloud disk deletion are not verified.
`SUCCESS` is printed only after SQL and cleanup finish, with exit code 0.
Errors print `FAILED` and return a nonzero exit code. SQL success means the query
executed without errors; the caller must evaluate whether its returned values
meet the expected result.
