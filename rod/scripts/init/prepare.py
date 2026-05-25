from rod.libs.py.tf.tfvars import (
    tfvars,
    TfVars,
    Env,
    Network,
    update_tfvars,
    TfBackend,
    Dns,
    Registry,
    env_network_settings,
    Location,
)
from rod.libs.py.settings import bazel_settings
import argparse

ALLOWED_ENVS = {
    "dev": "development",
    "stg": "staging",
    "prd": "production",
    "pre": "preprod",
    "sandbox": "sandbox",
}


def prepare_tfvars_gcp(tfvars: TfVars):
    envs = tfvars.envs
    tf_backend = {
        "type": "gcs",
        "configs": {
            "bucket": "{company.name}-tf-state",
            "prefix": "{env.name}/{tf_backend.state_name}",
        },
    }
    registry = {
        "type": "gar",
        "url": "{env.cloud.location.region}-docker.pkg.dev/{env.cloud.id}/containers",
    }
    dns = {"domain": "{env.short_name}.{company.domain}.", "type": "gcp"}
    location = {
        "region": "CHANGE_ME",
        "default_zone": "CHANGE_ME",
        "multi_region": "CHANGE_ME",
    }

    for env_name, env_obj in tfvars.envs.items():
        pod_cidr = env_obj.cloud.network.k8s_pod_cidr
        env_obj.cloud.name = "gcp"
        env_obj.tf_backend = TfBackend(**tf_backend)
        env_obj.registry = Registry(**registry)
        env_obj.dns = Dns(**dns)
        env_obj.cloud.location = Location(**location)
        env_obj.cloud.folder_id = ""
        env_obj.cloud.id = "CHANGE_ME"


def prepare_tfvars_yc(tfvars: TfVars):
    envs = tfvars.envs
    tf_backend = {
        "type": "s3",
        "configs": {
            "bucket": "{company.name}-tf-state",
            "use_lockfile": "true",
            "region": "{env.cloud.location.region}",
            "key": "{env.name}/{tf_backend.state_name}/default.tfstate",
            "skip_region_validation": "true",
            "skip_credentials_validation": "true",
            "skip_requesting_account_id": "true",
            "skip_s3_checksum": "true",
        },
    }
    registry = {"type": "ycr", "url": ""}
    dns = {"domain": "{env.short_name}.{company.domain}.", "type": "yc"}
    # We set locations for yc because there
    # is only one ru region and prefered location
    location = {
        "region": "ru-central1",
        "default_zone": "ru-central1-d",
        "multi_region": "",
    }
    for env_name, env_obj in tfvars.envs.items():
        pod_cidr = env_obj.cloud.network.k8s_pod_cidr
        env_obj.cloud.network.k8s_pod_cidr = pod_cidr.replace("/14", "/16")
        env_obj.cloud.name = "yc"
        env_obj.tf_backend = TfBackend(**tf_backend)
        env_obj.registry = Registry(**registry)
        env_obj.dns = Dns(**dns)
        env_obj.cloud.location = Location(**location)
        env_obj.kubernetes.regional = False
        # We set node_locations for yc because there
        # is only one ru region and prefered location
        env_obj.kubernetes.node_locations = ["ru-central1-d"]
        env_obj.cloud.id = "CHNAGE_ME"
        env_obj.cloud.folder_id = "CHANGE_ME"


def prepare_tfvars(cloud: str, poduct_env_names: dict[str, str]):
    tf_vars = tfvars()
    tf_vars.repo.name = "CHANGE_ME"
    tf_vars.repo.group = "CHANGE_ME"
    tf_vars.company.name = "CHANGE_ME"
    tf_vars.company.domain = "CHANGE_ME"
    envs = tf_vars.envs
    product_obj = None
    current_product_names = []
    for env_name, env_obj in envs.items():
        env_obj.cloud.network.vm_cidr = ""
        env_obj.cloud.network.k8s_pod_cidr = ""
        env_obj.cloud.network.k8s_service_cidr = ""
        if env_obj.type == "product":
            product_obj = env_obj.model_copy(deep=True)
            current_product_names.append(env_name)

    for env_name in current_product_names:
        envs.pop(env_name)

    for env_short_name, env_long_name in poduct_env_names.items():
        envs[env_long_name] = product_obj.model_copy(deep=True)
        envs[env_long_name].short_name = env_short_name
        envs[env_long_name].name = env_long_name

    for env_name, env_obj in envs.items():
        for app_name, app_obj in env_obj.apps.items():
            app_obj.repo = None
            app_obj.cd = None
        env_obj.initial_start = True
        env_obj.cloud.buckets.multi_regional = False
        env_obj.kubernetes.enabled = True
        env_obj.kubernetes.node_locations = ["CHANGE_ME"]
        if not env_obj.cloud.network:
            vm_net_str, pod_service_net_str, pod_net_str = env_network_settings(
                tf_vars.envs.values()
            )
            env_obj.cloud.network.vm_cidr = vm_net_str
            env_obj.cloud.network.k8s_pod_cidr = pod_net_str
            env_obj.cloud.network.k8s_service_cidr = pod_service_net_str

    if cloud == "gcp":
        prepare_tfvars_gcp(tf_vars)
    elif cloud == "yc":
        prepare_tfvars_yc(tf_vars)

    update_tfvars(tf_vars)


def main():
    def parse_envs(value: str) -> list[str]:
        envs = [env.strip() for env in value.split(",") if env.strip()]

        if not envs:
            raise argparse.ArgumentTypeError("at least one env is required")
        allowed_envs = ALLOWED_ENVS.keys()

        invalid = set(envs) - allowed_envs
        if invalid:
            allowed = ", ".join(sorted(allowed_envs))
            bad = ", ".join(sorted(invalid))
            raise argparse.ArgumentTypeError(
                f"invalid env(s): {bad}. Allowed values: {allowed}"
            )

        return envs

    # We use argparse instead of click bacause we
    # want to reuse parse_tfvars function
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "cloud",
        choices=["gcp", "yc"],
    )

    parser.add_argument(
        "--envs",
        type=parse_envs,
        default="prd",
        help=f"Comma-separated envs. Allowed: {list(ALLOWED_ENVS.keys())}",
    )
    envs = {}
    args = parser.parse_args()
    cloud = args.cloud
    for env in args.envs:
        envs[env] = ALLOWED_ENVS[env]

    prepare_tfvars(cloud, envs)


if __name__ == "__main__":
    main()
