import time

from kubernetes import client, stream
from kubernetes.client.exceptions import ApiException

from rod.libs.py.k8s.client import k8s_client_get
from rod.libs.py.tf.tfvars import Env


def get_error_details(error: Exception) -> str:
    """Return an error message with Kubernetes status and response details.

    Args:
        error: Exception to describe.

    Returns:
        Message suitable for command line logs.
    """
    if isinstance(error, ApiException):
        details = f"Kubernetes API returned {error.status}: {error.reason}"
        return f"{details}\n{error.body}" if error.body else details
    return str(error)


class PodCommandError(RuntimeError):
    """A Pod command failed with a nonzero exit code."""

    def __init__(
        self,
        namespace: str,
        pod: str,
        command: list[str],
        return_code: int,
        stdout: str,
        stderr: str,
    ):
        """Describe a failed command and include its captured output.

        Args:
            namespace: Namespace containing the Pod.
            pod: Pod where the command ran.
            command: Executed command and its arguments.
            return_code: Nonzero command exit code.
            stdout: Captured standard output.
            stderr: Captured standard error.
        """
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
    """Common Kubernetes operations used by command line tools."""

    def __init__(self, environment: Env):
        """Create a Kubernetes client for the selected environment.

        Args:
            environment: Environment with cloud and Kubernetes settings.
        """
        self.environment = environment
        self._client_created_at = time.monotonic()
        self._api = k8s_client_get(environment)

    @property
    def api(self):
        """Return the client, recreating it after 40 minutes.

        Returns:
            Kubernetes client for this environment.
        """
        now = time.monotonic()
        if now - self._client_created_at >= 40 * 60:
            old_api = self._api
            self._api = k8s_client_get(self.environment)
            self._client_created_at = now
            old_api.close()
        return self._api

    def list_resources(self, kind: str, namespace: str, selector: str) -> list[dict]:
        """List resources matching a label selector in one namespace.

        Args:
            kind: Resource type, such as pods or statefulsets.
            namespace: Namespace to search.
            selector: Kubernetes label selector.

        Returns:
            Resource dictionaries with their resource type in the kind field.

        Raises:
            KeyError: The resource type is unsupported.
        """
        api = self.api
        list_methods = {
            "pods": api.list_namespaced_pod,
            "statefulsets": api.list_namespaced_stateful_set,
            "services": api.list_namespaced_service,
            "endpoints": api.list_namespaced_endpoints,
            "endpointslices": api.list_namespaced_endpoint_slice,
            "configmaps": api.list_namespaced_config_map,
            "secrets": api.list_namespaced_secret,
            "jobs": api.list_namespaced_job,
            "deployments": api.list_namespaced_deployment,
            "replicasets": api.list_namespaced_replica_set,
            "persistentvolumeclaims": api.list_namespaced_persistent_volume_claim,
        }
        result = list_methods[kind](namespace, label_selector=selector)
        resources = [resource.to_dict() for resource in result.items]
        for resource in resources:
            resource["kind"] = kind
        return resources

    def delete_persistentvolumeclaims(self, namespace: str, selector: str) -> None:
        """Request deletion of PVCs matching a label selector.

        Args:
            namespace: Namespace containing the PVCs.
            selector: Kubernetes label selector identifying PVCs to delete.
        """
        self.api.delete_collection_namespaced_persistent_volume_claim(
            namespace,
            label_selector=selector,
            body=client.V1DeleteOptions(),
        )

    def exec_in_pod(
        self, namespace: str, pod: str, command: list[str], container: str
    ) -> str:
        """Run a command in the selected Pod container.

        Args:
            namespace: Namespace containing the Pod.
            pod: Pod name.
            command: Command and arguments, without shell interpretation.
            container: Name of the container where the command runs.

        Returns:
            Captured standard output.

        Raises:
            PodCommandError: The command exits with a nonzero code.
            RuntimeError: The command does not return an exit code.
        """
        response = stream.stream(
            self.api.v1.connect_get_namespaced_pod_exec,
            pod,
            namespace,
            command=command,
            container=container,
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
                namespace=namespace,
                pod=pod,
                command=command,
                return_code=return_code,
                stdout=stdout,
                stderr=stderr,
            )
        return stdout
