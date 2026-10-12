from kubernetes import client, config as k8s_config

from rod.libs.py.gcp.gke import gke_cluster_settings
from rod.libs.py.gcp.auth import get_creds
from rod.libs.py.k8s.config import (
    KubeConfig,
    NamedCluster,
    NamedContext,
    NamedAuthInfo,
    Cluster,
    AuthInfo,
    ExecConfig,
    Context,
    ExecInteractiveModeEnum,
)
from rod.libs.py.utils.logger import CliLogger, BaseLogger
from rod.libs.py.tf.tfvars import Env, CloudTypeEnum


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


def k8s_client_get(
    env: Env,
    logger: BaseLogger | None = None,
) -> K8sClient:
    if not logger:
        logger = CliLogger("rod.libs.py.k8s.client.k8s_client_get")
    config = kube_config_factory(env)
    api_client = k8s_config.load_kube_config_from_dict(config.model_dump())
    return K8sClient(
        v1=client.CoreV1Api(api_client),
        custom=client.CustomObjectsApi(api_client),
    )


def _gcp_kube_config(
    env: Env,
    global_name: str,
    cluster_name: str,
    use_exec: bool,
) -> KubeConfig:
    config = KubeConfig()
    cluster = gke_cluster_settings(
        env.cloud.id, env.cloud.location.region, cluster_name
    )

    config.clusters.append(
        NamedCluster(
            name=global_name,
            cluster=Cluster(
                server=cluster.endpoint, certificate_authority_data=cluster.ca_cert
            ),
        )
    )
    config.contexts.append(
        NamedContext(
            name=global_name, context=Context(cluster=global_name, user=global_name)
        )
    )

    named_user = NamedAuthInfo(
        name=global_name,
        user=AuthInfo(),
    )

    if use_exec:
        named_user.user.exec = ExecConfig(
            command="gke-gcloud-auth-plugin",
            interactiveMode=ExecInteractiveModeEnum.if_available,
            provideClusterInfo=True,
        )
    else:
        credentials = get_creds()
        named_user.user.token = credentials.token

    config.users.append(named_user)
    return config


def kube_config_factory(
    env: Env,
    company_name: str | None = None,
    cluster_name: str | None = None,
    use_exec: bool = False,
    logger: BaseLogger | None = None,
) -> KubeConfig:
    config = KubeConfig()
    global_name = f"{env.cloud.name.value}-{env.short_name}"
    if company_name:
        global_name = f"{company_name}-{env.cloud.name.value}-{env.short_name}"

    if not cluster_name:
        cluster_name = env.short_name.lower()
    if not logger:
        logger = CliLogger("rod.libs.py.k8s.client.k8s_config_factory")

    if env.cloud.name == CloudTypeEnum.gcp:
        config = _gcp_kube_config(env, global_name, cluster_name, use_exec)
    config.current_context = global_name
    print(config.model_dump_json(indent=2))

    return config
