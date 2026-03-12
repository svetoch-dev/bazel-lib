from libs.py.helpers import run_command, switch_index
from libs.py.settings import bazel_settings
from libs.py.utils.logger import CliLogger, BaseLogger
from pathlib import Path


def apply_env_targets(
    env: str,
    exclude_targets: list[str] | None = None,
) -> list[str] | None:
    """
    Finds Bazel apply targets for the given Terraform environment

    The function first queries Bazel for targets under the environment directory
    configured by ``bazel_settings.tf_env_dir``. Any targets listed in
    ``exclude_targets`` are skipped. Each remaining target is then
    executed with ``bazel run`` in sequence.

    Args:
        env: Name of the Terraform environment to apply.
        exclude_targets: Bazel targets that should be excluded from execution.
        logger: Logger instance used to report errors.

    Returns:
        list[str] list of apply targets for env
    """
    exclude_targets = exclude_targets or []

    search_path = f"{bazel_settings.tf_env_dir}/{env}"
    secrets_target = f"//{bazel_settings.tf_env_dir}/{env}/secrets:apply"
    cloud_target = f"//{bazel_settings.tf_env_dir}/{env}/cloud:apply"
    query = ["bazel", "query", f'attr(name, "^apply$|^rapply$", "//{search_path}/...")']
    return_code, stderr, apply_targets = run_command(query, print_stdout=False)

    apply_targets = [t for t in apply_targets if t not in exclude_targets]

    # Secrets target should be last
    switch_index(apply_targets, secrets_target, index=len(apply_targets) - 1)
    # Cloud target should be first
    switch_index(apply_targets, cloud_target, index=0)

    return apply_targets


def apply_env(
    env: str,
    exclude_targets: list[str] | None = None,
    logger: BaseLogger = CliLogger("scripts.init.tf.apply.apply_env"),
) -> bool:
    """
    Finds Bazel apply targets for the given Terraform environment and runs them.

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

    apply_targets = apply_env_targets(env, exclude_targets)

    if apply_targets == []:
        logger.error(f"No apply targets found for {env}")
        return False

    for target in apply_targets:
        command = ["bazel", "run", target]

        return_code, stderr, stdout = run_command(command)
        if return_code != 0:
            return False

    return True
