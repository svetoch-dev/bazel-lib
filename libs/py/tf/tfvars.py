from libs.py.settings import bazel_settings
from pydantic import BaseModel, ConfigDict
from libs.py.helpers import dict_to_dot_notation, replace_dotted_placeholders


class BaseTfVarsModel(BaseModel):

    model_config = ConfigDict(extra="forbid")


class Kubernetes(BaseTfVarsModel):
    enabled: bool
    regional: bool = False
    deletion_protection: bool = True
    node_locations: list[str] = []
    auth_group: str = ""


class User(BaseTfVarsModel):
    name: str
    roles: list[str]


class AppAccessRoles(BaseTfVarsModel):
    port_forward: str = "dev"


class ImportSecret(BaseTfVarsModel):
    name: str
    k8s_enabled: bool = True
    namespace: str
    base64_secrets: bool = False
    secrets_to_import: list[str]


class TfBackend(BaseTfVarsModel):
    type: str
    configs: dict[str, str]


class Buckets(BaseTfVarsModel):
    multi_regional: bool
    deletion_protection: bool = True


class Network(BaseTfVarsModel):
    vm_cidr: str
    k8s_pod_cidr: str
    k8s_service_cidr: str


class App(BaseTfVarsModel):
    name: str
    postgres: bool = False
    redis: bool = False
    rabbitmq: bool = False
    access_roles: AppAccessRoles = AppAccessRoles()


class Cloud(BaseTfVarsModel):
    name: str
    id: str
    folder_id: str | None = None
    region: str
    default_zone: str
    multi_region: str
    registry: str
    network: Network
    buckets: Buckets


class Env(BaseTfVarsModel):
    name: str
    short_name: str
    users: dict[str, User]
    apps: dict[str, App]
    import_secrets: dict[str, ImportSecret]
    tf_backend: TfBackend
    cloud: Cloud
    kubernetes: Kubernetes


class Company(BaseTfVarsModel):
    name: str
    domain: str


class Repo(BaseTfVarsModel):
    name: str
    type: str
    group: str


class Ci(BaseTfVarsModel):
    type: str
    group: str


class TfVars(BaseTfVarsModel):
    company: Company
    repo: Repo
    ci: Ci
    envs: dict[str, Env]


def tfvars():
    with open(bazel_settings.tfvars_file, "r") as f:
        content = f.read()

    return TfVars.model_validate_json(content)


def formatted_tfvars():
    tf_vars_dict = tfvars().model_dump()

    replacement_dict = {}

    for key, obj in tf_vars_dict.items():
        if key != "envs" and isinstance(obj, dict):
            replacement_dict = replacement_dict | dict_to_dot_notation(obj, key)

    for env_name, env_dict in tf_vars_dict["envs"].items():
        replacement_dict = replacement_dict | dict_to_dot_notation(env_dict, "env")

        tf_vars_dict["envs"][env_name] = replace_dotted_placeholders(
            env_dict, replacement_dict
        )

    return TfVars.model_validate(tf_vars_dict)
