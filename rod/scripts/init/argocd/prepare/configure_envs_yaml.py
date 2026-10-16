import yaml
import sys

from rod.libs.py.settings import common_paths
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.k8s.client import kube_config_factory
from rod.libs.py.utils.logger import CliLogger
from rod.libs.py.k8s.exceptions import K8sClusterNotFound, K8sClusterPermissionsDenied
from rod.libs.py.cloud import nat_gw_ips
from rod.libs.py.cloud.exceptions import CloudPermissionsDenied


def configure_envs_yaml():
    """
    Write discovered cluster endpoints and the internal NAT IP to envs.yaml.

    Reads the existing Argo CD values file and updates entries for environments
    with Kubernetes enabled. The internal environment uses the in-cluster API
    address; product endpoints are discovered from their cloud providers.
    Product clusters that cannot be read are logged and skipped.

    NAT gateway discovery failures, including permission errors and a missing
    internal environment, are logged and fall back to the placeholder address
    "0.0.0.0".
    """
    logger = CliLogger("rod.scripts.init.argocd.prepare.configure_envs_yaml")
    tfvars = formatted_tfvars()
    envs_yaml_file = common_paths.argocd_dir + "/envs.yaml"
    envs_yaml = {"global": {"envs": {}}}

    with open(envs_yaml_file, "r") as f:
        result = yaml.safe_load(f)
        if isinstance(result, dict):
            envs_yaml = envs_yaml | result

    int_env = next((e for e in tfvars.envs.values() if e.type == "internal"), None)

    int_nat_gw = "0.0.0.0"
    try:
        int_nat_gw = nat_gw_ips(int_env)[0]
    except CloudPermissionsDenied as e:
        logger.error(str(e))
    except AttributeError as ea:
        logger.error(str(ea))

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
                    "int_nat_gw": int_nat_gw
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
