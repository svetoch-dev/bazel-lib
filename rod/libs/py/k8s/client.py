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
    """Aggregates the standard Kubernetes API clients into a single object.

    Wraps an ``ApiClient`` together with all commonly used typed API
    implementations (core, apps, batch, networking, RBAC, and so on). Any
    attribute not explicitly stored is looked up on the wrapped API objects
    in turn, so the instance can be used as if it implemented every API group
    directly.

    Attributes:
        client: The underlying ``ApiClient`` shared by all API objects.
        v1: Core V1 API.
        custom: Custom objects API.
        apps: Apps V1 API.
        batch: Batch V1 API.
        networking: Networking V1 API.
        rbac: RBAC Authorization V1 API.
        storage: Storage V1 API.
        autoscaling: Autoscaling V1 API.
        policy: Policy V1 API.
        scheduling: Scheduling V1 API.
        coordination: Coordination V1 API.
        discovery: Discovery V1 API.
    """

    def __init__(
        self,
        client: client.ApiClient,
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
        self.client = client
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

    def close(self) -> None:
        """Close thread pools and HTTP connections for each underlying client."""
        # Resource APIs can share a client; close each client only once.
        api_clients = {
            resource_api.api_client
            for resource_api in (
                self.v1,
                self.custom,
                self.apps,
                self.batch,
                self.networking,
                self.rbac,
                self.storage,
                self.autoscaling,
                self.policy,
                self.scheduling,
                self.coordination,
                self.discovery,
            )
        }
        # self.client is a raw api client so
        # it does not have .api_client attr
        api_clients.add(self.client)
        for api_client in api_clients:
            api_client.close()
            api_client.rest_client.pool_manager.clear()

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
    use_exec: bool = False,
) -> K8sClient:
    """
    Build a K8sClient for the cluster associated with the given environment.

    Generates a kubeconfig for the environment via ``kube_config_factory``,
    loads it into the Kubernetes client configuration, and creates all typed
    API objects bound to that configuration.

    Args:
        env: Environment describing the cloud and target cluster.
        logger: Optional logger to use; a default one is created if omitted.

    Returns:
        A K8sClient with all API objects ready to use.
    """
    if not logger:
        logger = CliLogger("rod.libs.py.k8s.client.k8s_client_get")
    config = kube_config_factory(env, use_exec=use_exec)
    api_client = k8s_config.load_kube_config_from_dict(config.model_dump())
    return K8sClient(
        client=client.ApiClient(api_client),
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
    """
    Build a kubeconfig for a GKE cluster, either static-token or exec-based.

    Resolves the cluster endpoint and CA certificate from the GCP project.
    With ``use_exec``, the config authenticates through the
    ``gke-gcloud-auth-plugin`` exec plugin; otherwise a static OAuth token is
    fetched from application default credentials.

    Args:
        env: Environment describing the cloud and target cluster.
        global_name: Name for the cluster, context, and user entries.
        cluster_name: Name of the cluster within the GCP project.
        use_exec: Whether to use the exec auth plugin instead of a static token.
        logger: Optional logger to use; a default one is created if omitted.

    Returns:
        A KubeConfig with single cluster, context, and user entries.
    """
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
    """
    Build a kubeconfig for a Yandex Cloud cluster, token or exec-based.

    Resolves the cluster endpoint and CA certificate from the YC folder.
    With ``use_exec``, the config authenticates via ``yc k8s create-token``
    exec plugin; otherwise a static token is taken from YC settings.

    Args:
        env: Environment describing the cloud and target cluster.
        global_name: Name for the cluster, context, and user entries.
        cluster_name: Name of the cluster within the YC folder.
        use_exec: Whether to use the exec auth plugin instead of a static token.
        logger: Optional logger to use; a default one is created if omitted.

    Returns:
        A KubeConfig with single cluster, context, and user entries.
    """
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
    """
    Create a KubeConfig for the cluster associated with the given environment.

    Builds the global config name from the cloud and environment short names,
    optionally prefixed with a company name. Dispatches to the cloud-specific
    builder based on the cloud type (GCP or YC). The current context is set
    to the global name.

    Args:
        env: Environment describing the cloud and target cluster.
        company_name: Optional prefix prepended to the global config name.
        cluster_name: Cluster name; defaults to the environment short name
            in lowercase.
        use_exec: Whether to use exec-based authentication instead of a
            static token.
        logger: Optional logger to use; a default one is created if omitted.

    Returns:
        A fully populated KubeConfig with the current context set.

    Raises:
        NotImplementedError: If the cloud type is not supported.
    """
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
        raise NotImplementedError(
            f"kube_config not implemented for {env.cloud.name.value}"
        )
    config.current_context = global_name

    return config
