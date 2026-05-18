import os
from rod.libs.py.helpers import run_command
from rod.libs.py.settings import bazel_settings
from rod.libs.py.utils.logger import CliLogger
from rod.libs.py.tf.tfvars import formatted_tfvars


def update_tfvars() -> bool:
    logger = CliLogger("rod.libs.py.tf.poststeps.update_tfvars")
    tfvars = formatted_tfvars()
    os.chdir(bazel_settings.workspace)

    for env_name, env_obj in tfvars.envs.items():
        search_path = f"//{bazel_settings.tf_env_dir}/{env_name}/..."
        query = ["bazel", "query", f'attr(name, "^tfvars_update$", "{search_path}")']
        return_code, stderr, targets = run_command(query, print_stdout=False)
        for target in targets:
            logger.info(f"found tfvars_update target {target} executing")
            return_code, stderr, targets = run_command(
                ["bazel", "run", target], print_stdout=False
            )
            if return_code != 0:
                logger.error(f"tfvars_update failed with exit_code={return_code}")


if __name__ == "__main__":
    update_tfvars()
