from kubernetes import client

from rod.libs.py.tf.tfvars import Env, CloudTypeEnum
from rod.libs.py.gcp.gke import gke_cluster_settings
from rod.libs.py.utils.logger import CliLogger, BaseLogger


class K8sClient:
    def __init__(self, v1: client.CoreV1Api, custom: client.CustomObjectsApi):
        self.v1 = v1
        self.custom = custom

    def __getattr__(self, name):
        for obj in (self.v1, self.custom):
            try:
                return getattr(obj, name)
            except AttributeError:
                pass

        raise AttributeError(f"'{type(self).__name__}' has no attribute '{name}'")


# def k8s_client(env: Env) -> K8sClient:
#    client.CoreV1Api()
#    return K8sClient()


def k8s_config_factory(
    env: Env,
    cluster_name: str | None = None,
    use_cli: bool = False,
    logger: BaseLogger | None = None,
) -> client.Configuration:
    config = client.Configuration()
    if not cluster_name:
        cluster_name = env.short_name.lower()
    if not logger:
        logger = CliLogger("rod.libs.py.k8s.client.k8s_config_factory")
    if env.cloud.name == CloudTypeEnum.gcp:
        cluster = gke_cluster_settings(
            env.cloud.id, env.cloud.location.region, cluster_name
        )
        config.host = cluster.endpoint
        config.cert_file = cluster.ca_cert

    return config
