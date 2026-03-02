from pydantic import BaseModel


class Kubernetes(BaseModel):
    enabled: bool = False
    regional: bool = False
    deletion_protection: bool = False
    node_locations: list[str] = []
    auth_group: str = ""


class User(BaseModel):
    name: str
    roles: list[str]


class AppAccessRoles(BaseModel):
    port_forward: str = "dev"


class ImportSecret(BaseModel):
    name: str
    k8s_enabled: bool = True
    namespace: str
    base64_secrets: bool = False
    secrets_to_import: list[str]


class TfBackend(BaseModel):
    type: str
    configs: dict[str, str]


class Buckets(BaseModel):
    deletion_protection: bool = True
    multi_regional: bool = False


class Network(BaseModel):
    vm_cidr: str
    k8s_pod_cidr: str
    k8s_service_cidr: str


class App(BaseModel):
    name: str
    postgres: bool = False
    redis: bool = False
    rabbitmq: bool = False
    access_roles: AppAccessRoles = AppAccessRoles()


class Cloud(BaseModel):
    name: str
    id: str
    folder_id: str | None = None
    region: str
    default_zone: str
    multi_region: str
    registry: str
    network: Network
    buckets: Buckets = Buckets()


class Env(BaseModel):
    name: str
    short_name: str
    users: dict[str, User]
    apps: dict[str, App]
    import_secrets: dict[str, ImportSecret]
    tf_backend: TfBackend
    cloud: Cloud
    kubernetes: Kubernetes


class Company(BaseModel):
    name: str
    domain: str


class Repo(BaseModel):
    type: str
    group: str


class Ci(BaseModel):
    type: str
    group: str


class TfVars(BaseModel):
    company: Company
    repo: Repo
    ci: Ci
    envs: dict[str, Env]


with open("terraform.tfvars.json", "r") as f:
    content = f.read()

tf_vars = TfVars.model_validate_json(content)
