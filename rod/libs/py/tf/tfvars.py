from typing import Literal

from rod.libs.py.settings import bazel_settings
from pydantic import BaseModel, ConfigDict, model_validator
from rod.libs.py.helpers import dict_to_dot_notation, replace_dotted_placeholders


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


class Registry(BaseTfVarsModel):
    type: Literal["ycr", "gar"]
    url: str


class Dns(BaseTfVarsModel):
    domain: str
    type: Literal["gcp", "yc"]


class Buckets(BaseTfVarsModel):
    multi_regional: bool
    deletion_protection: bool = True


class Location(BaseTfVarsModel):
    region: str
    default_zone: str
    multi_region: str = ""


class Network(BaseTfVarsModel):
    vm_cidr: str
    k8s_pod_cidr: str
    k8s_service_cidr: str


class CiApp(BaseTfVarsModel):
    repo_name: str
    repo_group: str
    cd_branch: str = ""
    cd_file: str = ""
    cd_path: str = ""
    vars: dict[str, str] = {}
    secrets: dict[str, str] = {}



class App(BaseTfVarsModel):
    name: str
    postgres: bool = False
    redis: bool = False
    rabbitmq: bool = False
    access_roles: AppAccessRoles = AppAccessRoles()
    ci: dict[str, CiApp] = {}



class Cloud(BaseTfVarsModel):
    name: Literal["gcp", "yc"]
    id: str
    folder_id: str | None = None
    location: Location
    network: Network
    buckets: Buckets

    @model_validator(mode="after")
    def validate_folder_id_for_yc(self):
        if self.name == "yc" and not self.folder_id:
            raise ValueError("folder_id must be set when cloud.name is yc")

        return self


class Env(BaseTfVarsModel):
    name: str
    short_name: str
    type: Literal["internal", "product"]
    initial_start: bool = False
    users: dict[str, User]
    apps: dict[str, App]
    import_secrets: dict[str, ImportSecret]
    registry: Registry
    dns: Dns
    tf_backend: TfBackend
    cloud: Cloud
    kubernetes: Kubernetes


class Company(BaseTfVarsModel):
    name: str
    domain: str


class Repo(BaseTfVarsModel):
    name: str
    type: Literal["github", "gitlab"]
    group: str


class Ci(BaseTfVarsModel):
    type: Literal["gl", "gha"]
    bazelisk_img_version: str = ""


class TfVars(BaseTfVarsModel):
    company: Company
    repo: Repo
    ci: Ci
    envs: dict[str, Env]

    @model_validator(mode="after")
    def validate_single_internal_env(self):
        internal_envs = [
            env_name
            for env_name, env_obj in self.envs.items()
            if env_obj.type == "internal"
        ]

        if len(internal_envs) != 1:
            raise ValueError('exactly one env type must be "internal"')

        return self


def tfvars():
    with open(bazel_settings.tfvars_file, "r") as f:
        content = f.read()

    return TfVars.model_validate_json(content)


def env_key(env: Env, tf_vars: TfVars) -> str:
    """
    Given an Env obj find its key in TfVars.envs dict

    Args:
    * env - Env obj
    * tf_vars - TfVars obj

    Retrurns:
    * key of found env object
    """
    return [k for k, v in tf_vars.envs.items() if v == env][0]


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
