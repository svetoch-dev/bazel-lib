from kubernetes import client, config as k8s_config

from rod.libs.py.gcp.k8s import GcpK8sCluster
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
from rod.libs.py.yc.k8s import YcK8sCluster
from rod.libs.py.yc.client import YcSettings


class K8sClient:
    def __init__(
        self,
        v1: client.CoreV1Api,
        custom: client.CustomObjectsApi,
        apps: client.AppsV1Api,
        batch: client.BatchV1Api,
        networking: client.NetworkingV1Api,
        rbac: client.RbacAuthorizationV1Api,
        storage: client.StorageV1Api,
        autoscaling: client.AutoscalingV1Api,
        policy: client.PolicyV1Api,
        scheduling: client.SchedulingV1Api,
        coordination: client.CoordinationV1Api,
        discovery: client.DiscoveryV1Api,
    ):
        self.v1 = v1
        self.custom = custom
        self.apps = apps
        self.batch = batch
        self.networking = networking
        self.rbac = rbac
        self.storage = storage
        self.autoscaling = autoscaling
        self.policy = policy
        self.scheduling = scheduling
        self.coordination = coordination
        self.discovery = discovery

    def __getattr__(self, name):
        for obj in (
            self.v1,
            self.apps,
            self.custom,
            self.batch,
            self.networking,
            self.rbac,
            self.storage,
            self.autoscaling,
            self.policy,
            self.scheduling,
            self.coordination,
            self.discovery,
        ):
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
        apps=client.AppsV1Api(api_client),
        batch=client.BatchV1Api(api_client),
        networking=client.NetworkingV1Api(api_client),
        rbac=client.RbacAuthorizationV1Api(api_client),
        storage=client.StorageV1Api(api_client),
        autoscaling=client.AutoscalingV1Api(api_client),
        policy=client.PolicyV1Api(api_client),
        scheduling=client.SchedulingV1Api(api_client),
        coordination=client.CoordinationV1Api(api_client),
        discovery=client.DiscoveryV1Api(api_client),
    )


def _gcp_kube_config(
    env: Env,
    global_name: str,
    cluster_name: str,
    use_exec: bool,
    logger: BaseLogger | None = None,
) -> KubeConfig:
    config = KubeConfig()
    logger = logger or CliLogger("rod.libs.py.k8s.client._gcp_kube_config")
    location = env.cloud.location.region
    if not env.kubernetes.regional:
        location = env.cloud.location.default_zone

    cluster = GcpK8sCluster(env.cloud.id, cluster_name, location)

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


def _yc_kube_config(
    env: Env,
    global_name: str,
    cluster_name: str,
    use_exec: bool,
    logger: BaseLogger | None = None,
) -> KubeConfig:
    config = KubeConfig()
    logger = logger or CliLogger("rod.libs.py.k8s.client._yc_kube_config")
    cluster = YcK8sCluster(
        env.cloud.folder_id,
        cluster_name,
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
            command="yc",
            args=["k8s", "create-token"],
            interactiveMode=ExecInteractiveModeEnum.if_available,
            provideClusterInfo=False,
        )
    else:
        named_user.user.token = YcSettings().token

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
    logger = logger or CliLogger("rod.libs.py.k8s.client.k8s_config_factory")
    global_name = f"{env.cloud.name.value}-{env.short_name}"
    if company_name:
        global_name = f"{company_name}-{env.cloud.name.value}-{env.short_name}"

    if not cluster_name:
        cluster_name = env.short_name.lower()

    if env.cloud.name == CloudTypeEnum.gcp:
        config = _gcp_kube_config(env, global_name, cluster_name, use_exec)
    elif env.cloud.name == CloudTypeEnum.yc:
        config = _yc_kube_config(env, global_name, cluster_name, use_exec)
    else:
        raise NotImplementedError(f"kube_config not implemented for {env.cloud.name}")
    config.current_context = global_name

    return config
