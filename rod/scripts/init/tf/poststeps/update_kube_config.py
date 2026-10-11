# from rod.libs.py.settings import bazel_settings
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.utils.logger import CliLogger


def update_kube_config() -> bool:
    logger = CliLogger("rod.libs.py.tf.poststeps.update_kube_config")
    tfvars = formatted_tfvars()

    for env_obj in tfvars.envs.values():
        print(env_obj)

    logger.info("hui")

    return True


if __name__ == "__main__":
    update_kube_config()
