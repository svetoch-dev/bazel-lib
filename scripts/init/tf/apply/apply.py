import os
import sys
from libs.py.settings import bazel_settings
from libs.py.tf.tfvars import tfvars
from libs.py.utils.logger import CliLogger
from scripts.init.tf.apply.env import apply_env
from pathlib import Path


def apply() -> None:
    os.chdir(bazel_settings.workspace)
    logger = CliLogger("scripts.init.tf.apply.apply")
    tf_vars = tfvars()

    envs = []

    for env_name, env_obj in tf_vars.envs.items():
        # Some resources cant be applied because they
        # depend on other root module. So what we do is
        # 1. Add logic in modules not to create them
        # if initial_start = True
        # 2. At the begining in terraform.tfvars.json,
        # set initial_start = True
        # 3. Apply everything
        # 4. Dump a new version of terraform.tfvars.json with
        # initial_start = False
        # 5. Apply everything again
        env_obj.initial_start = False
        # We need to apply all apply targets for int env
        # first then for all others.
        if env_obj.short_name == "int":
            if len(envs) != 0:
                env_buffer = envs[0]
                envs[0] = env_obj
                envs.append(env_buffer)
                continue

        envs.append(env_obj)

    for env_obj in envs:
        # We exclude secrets because we have a dedicated apply
        # secret step
        secrets_target = f"//{bazel_settings.tf_env_dir}/{env_obj.name}/secrets:apply"
        applied = apply_env(env_obj.name, exclude_targets=[secrets_target])
        if not applied:
            logger.error(f"Failed to apply tf for {env_obj.name}")
            sys.exit(1)

    # Dump new terraform.tfvars.json with initial_start = False
    Path(bazel_settings.tfvars_file).write_text(
        tf_vars.model_dump_json(indent=2),
        encoding="utf-8",
    )

    # Re apply everything again
    for env_obj in envs:
        # We exclude secrets because we have a dedicated apply
        # secret step
        secrets_target = f"//{bazel_settings.tf_env_dir}/{env_obj.name}/secrets:apply"
        applied = apply_env(env_obj.name, exclude_targets=[secrets_target])
        if not applied:
            logger.error(f"Failed to apply tf for {env_obj.name}")
            sys.exit(1)


if __name__ == "__main__":
    apply()
