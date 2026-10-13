from google.cloud import container_v1
from google.api_core.exceptions import NotFound, PermissionDenied

from rod.libs.py.k8s.exceptions import K8sClusterNotFound, K8sClusterPermissionsDenied
from rod.libs.py.settings import K8sClusterSettings
from rod.libs.py.utils.logger import BaseLogger, CliLogger
from rod.libs.py.gcp.auth import get_creds, get_caller_email


class GcpK8sCluster(K8sClusterSettings):
    def __init__(
        self,
        project_id: str,
        name: str,
        location: str,
        logger: BaseLogger | None = None,
    ):
        logger = logger or CliLogger("rod.libs.py.gcp.k8s.GcpK8sCluster")
        self.project_id = project_id
        self.name = name
        self.location = location
        self.logger = logger

        self._cluster = self._get()

    def __getattr__(self, name):
        return getattr(self._cluster, name)

    @property
    def endpoint(self):
        return f"https://{self._cluster.endpoint}"

    @property
    def ca_cert(self):
        return self._cluster.master_auth.cluster_ca_certificate

    def _get(self):
        """Return the k8s cluster named by this instance, or raises an exception when missing."""

        client = container_v1.ClusterManagerClient()

        try:
            return client.get_cluster(
                name=f"projects/{self.project_id}/locations/{self.location}/clusters/{self.name}"
            )
        except NotFound:
            raise K8sClusterNotFound(
                f"Cluster {self.name} in project {self.project_id} and location {self.location} not found"
            )
        except PermissionDenied as e:
            creds = get_creds()
            email = get_caller_email(creds)
            raise K8sClusterPermissionsDenied(f"{email} {str(e)}")
