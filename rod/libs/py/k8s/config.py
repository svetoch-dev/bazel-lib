"""Models for the Kubernetes client-go v1 kubeconfig file format."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class ExecInteractiveModeEnum(str, Enum):
    never = "Never"
    if_available = "IfAvailable"
    always = "Always"


class BaseKubeConfigModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    def model_dump(self, **kwargs):
        kwargs.setdefault("exclude_none", True)
        kwargs.setdefault("mode", "json")

        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)

    def model_dump_json(self, **kwargs):
        kwargs.setdefault("exclude_none", True)

        kwargs.setdefault("by_alias", True)
        return super().model_dump_json(**kwargs)


class NamedExtension(BaseKubeConfigModel):
    name: str
    extension: JsonValue


class Preferences(BaseKubeConfigModel):
    colors: bool | None = None
    extensions: list[NamedExtension] | None = None


class Cluster(BaseKubeConfigModel):
    server: str
    tls_server_name: str | None = Field(default=None, alias="tls-server-name")
    insecure_skip_tls_verify: bool | None = Field(
        default=None, alias="insecure-skip-tls-verify"
    )
    certificate_authority: str | None = Field(
        default=None, alias="certificate-authority"
    )
    certificate_authority_data: str | None = Field(
        default=None, alias="certificate-authority-data"
    )
    proxy_url: str | None = Field(default=None, alias="proxy-url")
    disable_compression: bool | None = Field(default=None, alias="disable-compression")
    extensions: list[NamedExtension] | None = None


class AuthProviderConfig(BaseKubeConfigModel):
    name: str
    config: dict[str, str] = Field(default_factory=dict)


class ExecEnvVar(BaseKubeConfigModel):
    name: str
    value: str


class ExecConfig(BaseKubeConfigModel):
    command: str
    args: list[str] | None = None
    env: list[ExecEnvVar] | None = None
    api_version: str = Field(
        default="client.authentication.k8s.io/v1beta1", alias="apiVersion"
    )
    install_hint: str | None = Field(default=None, alias="installHint")
    provide_cluster_info: bool | None = Field(default=None, alias="provideClusterInfo")
    interactive_mode: ExecInteractiveModeEnum | None = Field(
        default=None, alias="interactiveMode"
    )


class AuthInfo(BaseKubeConfigModel):
    client_certificate: str | None = Field(default=None, alias="client-certificate")
    client_certificate_data: str | None = Field(
        default=None, alias="client-certificate-data"
    )
    client_key: str | None = Field(default=None, alias="client-key")
    client_key_data: str | None = Field(default=None, alias="client-key-data")
    token: str | None = None
    token_file: str | None = Field(default=None, alias="tokenFile")
    impersonate: str | None = Field(default=None, alias="as")
    impersonate_uid: str | None = Field(default=None, alias="as-uid")
    impersonate_groups: list[str] | None = Field(default=None, alias="as-groups")
    impersonate_user_extra: dict[str, list[str]] | None = Field(
        default=None, alias="as-user-extra"
    )
    username: str | None = None
    password: str | None = None
    auth_provider: AuthProviderConfig | None = Field(
        default=None, alias="auth-provider"
    )
    exec: ExecConfig | None = None
    extensions: list[NamedExtension] | None = None


class Context(BaseKubeConfigModel):
    cluster: str = ""
    user: str = ""
    namespace: str | None = None
    extensions: list[NamedExtension] | None = None


class NamedCluster(BaseKubeConfigModel):
    name: str
    cluster: Cluster


class NamedAuthInfo(BaseKubeConfigModel):
    name: str
    user: AuthInfo


class NamedContext(BaseKubeConfigModel):
    name: str
    context: Context


class KubeConfig(BaseKubeConfigModel):
    kind: str = "Config"
    api_version: str = Field(default="v1", alias="apiVersion")
    preferences: Preferences = Field(default_factory=Preferences)
    clusters: list[NamedCluster] = Field(default_factory=list)
    users: list[NamedAuthInfo] = Field(default_factory=list)
    contexts: list[NamedContext] = Field(default_factory=list)
    current_context: str = Field(default="", alias="current-context")
    extensions: list[NamedExtension] | None = None
