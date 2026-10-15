import yaml

from rod.libs.py.settings import bazel_settings
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.k8s.client import kube_config_factory
from rod.libs.py.utils.logger import CliLogger
from rod.libs.py.k8s.exceptions import K8sClusterNotFound, K8sClusterPermissionsDenied


def configure_envs_yaml():
    logger = CliLogger("rod.scripts.init.argocd.prepare.configure_envs_yaml")
    tfvars = formatted_tfvars()
    envs_yaml_file = bazel_settings.argocd_dir + "/envs.yaml"
    envs_yaml = {"global": {"envs": {}}}
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
                    "int_nat_gw": None
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
