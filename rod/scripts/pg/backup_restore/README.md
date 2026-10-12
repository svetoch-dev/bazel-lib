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
- `kubectl` must be available in `PATH`, with an authenticated context pointing
  to the intended Kubernetes cluster.
- The Kubernetes user needs permission to get, list, create, and delete
  `postgresql` resources; list Pods, StatefulSets, PVCs, Services, Endpoints, EndpointSlices,
  ConfigMaps, Secrets, Jobs, Deployments, and ReplicaSets; execute commands in
  Pods (`create` on `pods/exec`); and delete PVCs in the selected namespace.
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
  --postgres vaults \
  --date '2024.01.07 00:00:00' \
  --query 'SELECT count(1) FROM farms'
```

`--postgres` can be a Kubernetes cluster name or a Postgres Operator `teamId`.
For example, `vaults` resolves to the cluster whose team ID is `vaults`. If
multiple clusters match, pass `--namespace` to narrow the lookup. Without
`--namespace`, the command searches all namespaces, so the active `kubectl`
context must allow listing PostgreSQL resources across namespaces.

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
`dexswap-gcp-prd-v2-postgres-cluster` becomes
`dexswap-gcp-prd-v2-pg-clone-<run_id>`. Long names are shortened to leave room for
operator-generated replica Service names, while keeping `teamId` intact. If the
team ID alone leaves insufficient room for the clone suffix, the command fails
before creating the clone.

The command waits until the restored cluster becomes ready, runs the query, and
then removes the temporary cluster. It has no built-in timeout; if the cluster
does not become ready, the command keeps waiting.

SQL results include column headings. The command waits for the PostgreSQL
resource to be deleted, removes retained PVCs, and waits for the listed resource
types carrying the temporary clone's `cluster-name` label to disappear.
Unlabelled resources and cloud disk deletion are not verified.
`SUCCESS` is printed only after SQL and cleanup finish, with exit code 0.
Errors print `FAILED` and return a nonzero exit code. SQL success means the query
executed without errors; the caller must evaluate whether its returned values
meet the expected result.
