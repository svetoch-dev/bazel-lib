import os
import sys
from rod.libs.py.tf.tfvars import tfvars
from rod.libs.py.tf.secrets import import_secrets
from rod.libs.py.utils.logger import CliLogger


def secrets() -> None:
    tf_vars = tfvars()
    logger = CliLogger("rod.scripts.init.tf.secrets.secrets")

    for env_name, env_obj in tf_vars.envs.items():
        imported = import_secrets(env_name, env_obj.import_secrets)
        if not imported:
            logger.error(f"Import for secrets of {env_name} has failed")
            sys.exit(1)


if __name__ == "__main__":
    secrets()
