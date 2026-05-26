from pathlib import Path

from rod.libs.py.settings import bazel_settings
from rod.libs.py.utils.logger import CliLogger
from rod.libs.py.tf.tfvars import formatted_tfvars, update_tfvars as tfvars_update
from rod.libs.py.yc.registry import YcRegistry


def update_tfvars() -> bool:
    """Refresh generated Terraform variable values after Terraform apply.

    Yandex Container Registry endpoints are derived from the actual registry ID
    so consumers can push images without relying on Terraform output targets.
    """
    logger = CliLogger("rod.libs.py.tf.poststeps.update_tfvars")
    tfvars = formatted_tfvars()

    for env_name, env_obj in tfvars.envs.items():
        if env_obj.registry.type == "ycr":
            logger.info(f"updating ycr registry url for {env_name}")
            registry = YcRegistry(
                env_obj.cloud.folder_id, "containers", create_if_missing=False
            )
            if registry:
                env_obj.registry.url = registry.endpoint

    tfvars_update(tfvars)

    return True


if __name__ == "__main__":
    update_tfvars()
