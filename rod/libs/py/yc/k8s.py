import base64

from yandex.cloud.k8s.v1.cluster_service_pb2 import ListClustersRequest
from yandex.cloud.k8s.v1.cluster_service_pb2_grpc import ClusterServiceStub

from rod.libs.py.yc.client import sdk_get
from rod.libs.py.utils.logger import BaseLogger, CliLogger
from rod.libs.py.settings import K8sClusterSettings


class YcClusterNotFound(BaseException):
    pass


class YcK8sCluster(K8sClusterSettings):
    def __init__(
        self,
        folder_id: str,
        name: str,
        token: str | None = None,
        logger: BaseLogger | None = None,
    ):
        logger = logger or CliLogger("rod.libs.py.yc.k8s.YcK8sCluster")

        self.sdk = sdk_get(token)
        self.folder_id = folder_id
        self.name = name
        self.logger = logger

        self._cluster = self._get()

    def __getattr__(self, name):
        return getattr(self._cluster, name)

    @property
    def endpoint(self) -> str:
        return self.master.endpoints.external_v4_endpoint

    @property
    def ca_cert(self) -> str:
        ca_cert = self.master.master_auth.cluster_ca_certificate
        return str(base64.b64encode(ca_cert.encode("utf-8")))

    def _get(self):
        """Return the k8s cluster named by this instance, or None when missing."""
        response = self.sdk.client(ClusterServiceStub).List(
            ListClustersRequest(
                folder_id=self.folder_id,
                filter=f'name="{self.name}"',
            )
        )

        for cl in response.clusters:
            return cl

        raise YcClusterNotFound(
            f"Cluser {self.name} not found in folder {self.folder_id}"
        )
