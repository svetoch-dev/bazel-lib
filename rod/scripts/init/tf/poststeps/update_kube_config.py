# from rod.libs.py.settings import bazel_settings
from rod.libs.py.k8s.client import k8s_config_factory
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.utils.logger import CliLogger


def update_kube_config() -> bool:
    logger = CliLogger("rod.libs.py.tf.poststeps.update_kube_config")
    tfvars = formatted_tfvars()

    for env_obj in tfvars.envs.values():
        config = k8s_config_factory(env_obj)

    logger.info(config.host)

    return True


if __name__ == "__main__":
    update_kube_config()
