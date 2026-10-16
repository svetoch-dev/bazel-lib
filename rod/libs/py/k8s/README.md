# Kubernetes helpers

These helpers connect to Kubernetes using an `Env` from `terraform.tfvars.json`.

| Module | Responsibility |
| --- | --- |
| `client.py` | Build cloud authentication settings, create `K8sClient`, and close its connections. |
| `api.py` | Refresh the client, list resources, delete PVCs, and run commands in Pods. |
| `postgres.py` | List, read, create, and delete PostgreSQL custom resources. |

## Client lifecycle

`k8s_client_get(environment)` creates a `K8sClient` for GCP or YC.
`KubernetesApi` uses this helper at startup and before an API operation if its
client is at least 40 minutes old. It closes the old client only after the
replacement is created successfully.

`K8sClient.close()` closes SDK thread pools and clears HTTP connection pools.
If several resource APIs share an SDK client, it is closed only once.
Recreating the client does not renew a token supplied through `YC_TOKEN`.

## Resource operations

`list_resources(kind, namespace, selector)` returns resource dictionaries
matching the label selector in the given namespace.

`delete_persistentvolumeclaims(namespace, selector)` requests deletion of PVCs
matching the selector in that namespace. It does not wait for deletion or
check ownership. The caller must choose the selector and handle those checks.
`KubernetesPostgresApi` inherits these common methods from `KubernetesApi`.

## Pod commands and errors

`exec_in_pod(namespace, pod, command, container)` requires an explicit container
name. Pass command arguments as a list; they are not interpreted by a shell.
For example, the backup check passes `container="postgres"`.

The method returns stdout on success. A nonzero exit code raises
`PodCommandError`, which includes the namespace, Pod, command, exit code,
stdout, and stderr. A missing exit code raises `RuntimeError`.
The WebSocket is closed after execution, including when execution or reading
the output fails.

`get_error_details(error)` formats Kubernetes API errors with their status,
reason, and response body. For other exceptions, it returns their text.
