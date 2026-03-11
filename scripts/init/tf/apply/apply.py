import os
import sys
from libs.py.helpers import run_command
from libs.py.settings import bazel_settings
from libs.py.tf.tfvars import tfvars
from libs.py.utils.logger import CliLogger, BaseLogger
from pathlib import Path


def apply_env(
    env: str,
    exclude_targets: list[str] | None = None,
    logger: BaseLogger = CliLogger("scripts.init.tf.apply.apply_env"),
) -> bool:
    """
    Finds Bazel apply targets for the given Terraform environment and runs them.

    The function first queries Bazel for targets under the environment directory
    configured by ``bazel_settings.tf_env_dir``. Any targets listed in 
    ``exclude_targets`` are skipped. Each remaining target is then 
    executed with ``bazel run`` in sequence.

    Args:
        env: Name of the Terraform environment to apply.
        exclude_targets: Bazel targets that should be excluded from execution.
        logger: Logger instance used to report errors.

    Returns:
        ``True`` if at least one apply target is found and all target runs
        succeed. ``False`` if no matching targets are found or if any target
        execution fails.
    """

    exclude_targets = exclude_targets or []

    search_path = f"{bazel_settings.tf_env_dir}/{env}"
    query = ["bazel", "query", f'attr(name, "^apply$|^rapply$", "//{search_path}/...")']
    return_code, stderr, apply_targets = run_command(query, print_stdout=False)

    apply_targets = [t for t in apply_targets if t not in exclude_targets]

    if apply_targets == []:
        logger.error(f"No apply targets found for {env}")
        return False

    for target in apply_targets:
        command = ["bazel", "run", target]

        return_code, stderr, stdout = run_command(command)
        if return_code != 0:
            return False

    return True


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
