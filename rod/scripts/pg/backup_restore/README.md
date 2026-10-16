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
  environment. Pass its key with the required `--environment` option. Valid
  values are the keys of enabled Kubernetes environments. The shared client
  currently supports GCP and YC environments.
- Cloud credentials must be available: Google Application Default Credentials
  for GCP, or `YC_TOKEN` / instance service account metadata for YC. The client
  connects directly to the Kubernetes API. No kubeconfig, `kubectl`,
  `gke-gcloud-auth-plugin`, or `yc` executable is required by the script.
  The client is created at startup through `k8s_client_get()`, which obtains a
  fresh GCP token. Before API calls, the script checks the age of its client
  and recreates it if 40 minutes have elapsed. This also rereads YC credentials.
  A token passed through `YC_TOKEN`
  is not renewed by recreating the client. Obtain a fresh `YC_TOKEN`
  before starting the check in CI and ensure it remains valid through cleanup.
- The Kubernetes user needs `get`, `list`, `create`, `delete`, and
  `deletecollection` on `postgresql` resources; `list` on Pods, StatefulSets,
  PVCs, Services, Endpoints, EndpointSlices, ConfigMaps, Secrets, Jobs,
  Deployments, and ReplicaSets; `get` and `create` on `pods/exec`; and `delete` plus
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
  --postgres example-postgres-cluster \
  --database example_database \
  --date '2026.01.07 00:00:00' \
  --k8s-resource-poll-interval-seconds 5 \
  --postgres-recovery-poll-interval-seconds 3 \
  --query 'SELECT count(1) FROM example_table'
```

The polling options are optional. Kubernetes resource readiness and cleanup
checks use `--k8s-resource-poll-interval-seconds` (default: 5 seconds);
PostgreSQL recovery checks
use `--postgres-recovery-poll-interval-seconds` (default: 3 seconds). Both
values must be positive whole numbers of seconds.

Replace `YOUR_ENVIRONMENT` with the key of an enabled Kubernetes environment
from `terraform.tfvars.json`. The command reports the available keys if the
value is invalid.

`--postgres` must be the exact PostgreSQL cluster name (`metadata.name`). If
the same name exists in multiple namespaces, pass `--namespace` to select one.
Without `--namespace`, the command searches all namespaces in the selected
environment, so its Kubernetes identity must be allowed to list PostgreSQL
resources across namespaces.

Pass the database to check with the required `--database` option. Timestamps
without a timezone are interpreted as UTC; ISO timestamps with an explicit
offset are also accepted. The temporary clone uses the
source cluster's PostgreSQL version and volume settings, with one instance.
The volume `selector` is omitted so Kubernetes can provision a new PVC for the
clone. Custom PostgreSQL parameters and other optional source cluster settings
are not carried over to the clone.

Temporary clone names preserve the beginning of the source cluster name. A
trailing `-postgres-cluster` becomes `-pg` before `-clone-<run_id>` is added.
For example:
`example-postgres-cluster` becomes `example-pg-clone-<run_id>`. Long names are
shortened to leave room for operator-generated replica Service names.

The command waits for a Ready master Pod, then polls `pg_is_in_recovery()` in
the `postgres` database until it returns `false`. The intervals are controlled
by `--k8s-resource-poll-interval-seconds` and
`--postgres-recovery-poll-interval-seconds`. Only then does it run the user's
query and remove the temporary cluster. A failed SQL probe or an unexpected
result fails the check and triggers cleanup. It has no built-in timeout, so
readiness, recovery, and cleanup waits can continue indefinitely.

SQL results include column headings. The command waits for the PostgreSQL
resource to be deleted, removes retained PVCs, and waits for the listed resource
types carrying the temporary clone's `cluster-name` label to disappear.
Unlabelled resources and cloud disk deletion are not verified.
`SUCCESS` is printed only after SQL and cleanup finish, with exit code 0.
Runtime failures print `FAILED` and return a nonzero exit code. Invalid command
line arguments are reported by `argparse` and also return a nonzero exit code.
SQL success means the query executed without errors; the caller must evaluate
whether its returned values meet the expected result.
