import os
import sys
from rod.libs.py.helpers import run_command
from rod.libs.py.settings import bazel_settings
from rod.libs.py.tf.tfvars import tfvars
from rod.libs.py.tf.secrets import import_secrets
from rod.libs.py.utils.logger import CliLogger


def secrets() -> None:
    tf_vars = tfvars()
    logger = CliLogger("rod.scripts.init.tf.secrets.secrets")

    for env_name, env_obj in tf_vars.envs.items():
        os.chdir(bazel_settings.workspace)
        secrets_package = f"//{bazel_settings.tf_env_dir}/{env_name}/secrets"
        query = ["bazel", "query", f'attr(name, "^tf$", "{secrets_package}")']
        exit_code, stderr, _ = run_command(query, print_stdout=False)
        if exit_code != 0:
           logger.info(f"{secrets_package}:tf target not found")
           continue


        imported = import_secrets(env_name, env_obj.import_secrets)
        if not imported:
            logger.error(f"Import for secrets of {env_name} has failed")
            sys.exit(1)


if __name__ == "__main__":
    secrets()
