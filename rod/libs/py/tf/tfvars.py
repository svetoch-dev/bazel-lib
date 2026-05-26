from typing import Literal
from pathlib import Path

from rod.libs.py.settings import bazel_settings
from pydantic import BaseModel, ConfigDict, model_validator
from rod.libs.py.helpers import dict_to_dot_notation, replace_dotted_placeholders
import ipaddress


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

    def __bool__(self) -> bool:
        return all(
            [
                self.vm_cidr,
                self.k8s_pod_cidr,
                self.k8s_service_cidr,
            ]
        )


class AppRepo(BaseTfVarsModel):
    name: str = ""
    group: str = ""


class AppCD(BaseTfVarsModel):
    branch: str = ""
    file: str = ""
    tag_path: str = ""


class App(BaseTfVarsModel):
    name: str
    postgres: bool = False
    redis: bool = False
    rabbitmq: bool = False
    access_roles: AppAccessRoles | None = None
    repo: AppRepo | None = None
    cd: AppCD | None = None


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
    test: bool = False
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


def update_tfvars(tf_vars: TfVars) -> None:
    Path(bazel_settings.tfvars_file).write_text(
        tf_vars.model_dump_json(indent=2),
        encoding="utf-8",
    )


def env_network_settings(envs: list[Env]) -> tuple[str, str, str]:
    """
    Allocate non-overlapping CIDR blocks for a new environment.

    Divides the 10.0.0.0/8 private range into /14 subnets. Each environment
    consumes two adjacent /14s: the first is subdivided into /20s for VM
    and service CIDRs, and the second is used as the pod CIDR.

    Existing environment networks are excluded from allocation by checking
    which /14 subnets overlap with their vm_cidr, service_cidr, or pod_cidr.

    Args:
        envs: Existing environments to exclude from allocation.

    Returns:
        Tuple of (vm_cidr, service_cidr, pod_cidr) strings.
    """
    pod_nets_to_exclude = []
    main_net = ipaddress.ip_network("10.0.0.0/8")
    pod_nets_total = sorted(main_net.subnets(new_prefix=14))
    pod_nets_need_removal = []
    pod_nets_available = []

    for env_obj in envs:
        if not env_obj.cloud.network:
            continue

        pod_net = ipaddress.ip_network(env_obj.cloud.network.k8s_pod_cidr)
        vm_net = ipaddress.ip_network(env_obj.cloud.network.vm_cidr)
        service_net = ipaddress.ip_network(env_obj.cloud.network.k8s_service_cidr)

        for index, p_net in enumerate(pod_nets_total):
            if (
                pod_net.overlaps(p_net)
                or vm_net.overlaps(p_net)
                or service_net.overlaps(p_net)
            ) and p_net not in pod_nets_need_removal:
                pod_nets_need_removal.append(p_net)

    for p_net in pod_nets_total:
        if p_net not in pod_nets_need_removal:
            pod_nets_available.append(p_net)

    pod_net_str = str(pod_nets_available[1])
    vm_and_service_nets = sorted(pod_nets_available[0].subnets(new_prefix=20))
    vm_net_str = str(vm_and_service_nets[0])
    pod_service_net_str = str(vm_and_service_nets[1])

    return vm_net_str, pod_service_net_str, pod_net_str
