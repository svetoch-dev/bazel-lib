import base64

from yandex.cloud.k8s.v1.cluster_service_pb2 import ListClustersRequest
from yandex.cloud.k8s.v1.cluster_service_pb2_grpc import ClusterServiceStub

from rod.libs.py.yc.client import sdk_get
from rod.libs.py.utils.logger import BaseLogger, CliLogger


class K8sCluster:
    def __init__(
        self,
        folder_id: str,
        name: str,
        token: str | None = None,
        logger: BaseLogger | None = None,
    ):
        logger = logger or CliLogger("rod.libs.py.yc.k8s.K8sCluster")

        self.sdk = sdk_get(token)
        self.folder_id = folder_id
        self.name = name
        self.logger = logger

        self._cluster = self._get()
        if self._cluster:
            self.logger.info(f"cluster {self.name} found")
        else:
            self.logger.info(f"cluster {self.name} not found")

    def __getattr__(self, name):
        return getattr(self._cluster, name)

    def __bool__(self):
        return self._cluster is not None

    @property
    def endpoint(self):
        return self.master.endpoints.external_v4_endpoint

    @property
    def ca_cert(self):
        ca_cert = self.master.master_auth.cluster_ca_certificate
        return base64.b64encode(ca_cert.encode("utf-8"))

    def _get(self):
        """Return the k8s cluster named by this instance, or None when missing."""
        self.logger.info(f"name={self.name}")
        response = self.sdk.client(ClusterServiceStub).List(
            ListClustersRequest(
                folder_id=self.folder_id,
                filter=f'name="{self.name}"',
            )
        )
        cluster = None
        for cl in response.clusters:
            cluster = cl

        return cluster
