from kubernetes import stream
from kubernetes.client.exceptions import ApiException

from rod.libs.py.k8s.client import k8s_client_get
from rod.libs.py.tf.tfvars import Env


def error_details(error: Exception) -> str:
    if isinstance(error, ApiException):
        details = f"Kubernetes API returned {error.status}: {error.reason}"
        if error.body:
            details += f"\n{error.body}"
        return details
    return str(error)


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
    """Common Kubernetes operations used by command line tools."""

    def __init__(self, environment: Env):
        self.api = k8s_client_get(environment, use_exec=True)
        # Exec uses WebSockets and changes the API client's request protocol.
        self.exec_core = k8s_client_get(environment, use_exec=True).v1

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
