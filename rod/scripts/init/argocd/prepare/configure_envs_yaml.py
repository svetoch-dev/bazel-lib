import yaml

from rod.libs.py.settings import common_paths
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.k8s.client import kube_config_factory
from rod.libs.py.utils.logger import CliLogger
from rod.libs.py.k8s.exceptions import K8sClusterNotFound, K8sClusterPermissionsDenied
from rod.libs.py.helpers.cloud import nat_gw_ips


def configure_envs_yaml():
    logger = CliLogger("rod.scripts.init.argocd.prepare.configure_envs_yaml")
    tfvars = formatted_tfvars()
    envs_yaml_file = common_paths.argocd_dir + "/envs.yaml"
    envs_yaml = {"global": {"envs": {}}}
    with open(envs_yaml_file, "r") as f:
        result = yaml.safe_load(f)
        if isinstance(result, dict):
            envs_yaml = envs_yaml | result
    for env_name, env_obj in tfvars.envs.items():
        if not env_obj.kubernetes.enabled:
            continue

        k8s_server = "https://kubernetes.default.svc"

        if env_obj.type == "product":
            try:
                config = kube_config_factory(env_obj)
            except (K8sClusterNotFound, K8sClusterPermissionsDenied) as e:
                logger.error(str(e))
                continue

            cloud_short_name = f"{env_obj.cloud.name.value}-{env_obj.short_name}"
            k8s_server = next(
                (
                    c.cluster.server
                    for c in config.clusters
                    if c.name == cloud_short_name
                ),
                None,
            )

        # fmt: off
        env = {
            "cloud": {
                "network": {
                    "int_nat_gw": nat_gw_ips(env_obj)[0]
                }
            },
            "kubernetes": {
                "server": k8s_server
            }
        }
        # fmt: on

        envs_yaml["global"]["envs"][env_name] = env

    with open(envs_yaml_file, "w") as f:
        yaml.safe_dump(envs_yaml, f, sort_keys=False)


if __name__ == "__main__":
    configure_envs_yaml()
