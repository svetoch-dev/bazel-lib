import os
from rod.libs.py.helpers import run_command
from rod.libs.py.tf.tfvars import ImportSecret
from rod.libs.py.settings import bazel_settings
from rod.libs.py.utils.logger import CliLogger, BaseLogger


def render_tpl(
    tpl: str,
    secret_name: str,
    secret_key: str,
) -> str:
    """Render the secret name and key placeholders in a Terraform resource template.

    Args:
        tpl: Template containing ``<secret_name>`` and ``<secret_key>`` placeholders.
        secret_name: Secret name to insert into the template.
        secret_key: Secret key to insert into the template.

    Returns:
        The rendered Terraform resource address.
    """
    rendered = tpl.replace("<secret_name>", secret_name)
    rendered = rendered.replace("<secret_key>", secret_key)
    return rendered


def import_secret_env_name(
    secret_name: str,
    secret_key: str,
) -> str:
    """Build the environment-variable name used to read a secret value.

    Hyphens are converted to double underscores before the result is converted
    to uppercase.

    Args:
        secret_name: Name of the secret.
        secret_key: Key within the secret.

    Returns:
        The normalized ``TF_IMPORT_SECRET_*`` environment-variable name.
    """
    env_secret_name = secret_name.replace("-", "__")
    env_secret_key = secret_key.replace("-", "__")
    return f"TF_IMPORT_SECRET_{env_secret_name}_{env_secret_key}".upper()


def import_secrets(
    env: str,
    secrets: dict[str, ImportSecret],
    logger: BaseLogger = None,
    final_apply: bool = True,
    secrets_package: str = "secrets",
    tf_resource_tpl: str = 'module.secrets.module.rod_secrets["<secret_name>"].module.import_secret["<secret_key>"].secret_resource.secret',
) -> bool:
    """Import missing secrets into a Terraform state through Bazel targets.

    Secret values are read from normalized ``TF_IMPORT_SECRET_*`` environment
    variables. If a variable is absent, the user is prompted for its value.

    Args:
        env: Environment directory containing the secrets package.
        secrets: Secret definitions and the keys that should be imported.
        logger: Logger used for status and error messages.
        final_apply: Whether to run the package's apply target after imports.
        secrets_package: Package path relative to the environment directory.
        tf_resource_tpl: Terraform resource address template containing
            ``<secret_name>`` and ``<secret_key>`` placeholders.

    Returns:
        True when state inspection and all requested operations succeed; False
        when state inspection, an import, or the final apply fails.
    """
    logger = logger or CliLogger("rod.libs.py.tf.secrets.import_secrets")

    os.chdir(bazel_settings.workspace)
    secrets_package_full_path = f"//{bazel_settings.tf_env_dir}/{env}/{secrets_package}"
    state_list_command = [
        "bazel",
        "run",
        f"{secrets_package_full_path}:tf",
        "state",
        "list",
    ]
    exit_code, stderr, tf_resources = run_command(
        state_list_command, print_stdout=False
    )
    if exit_code != 0:
        logger.error(f"State list failed for {secrets_package_full_path}")
        return False

    final_apply_needed = False

    for secret_name, secret_obj in secrets.items():
        for secret_key in secret_obj.secrets_to_import:
            tf_resource = render_tpl(tf_resource_tpl, secret_name, secret_key)
            env_var_name = import_secret_env_name(secret_name, secret_key)
            import_command = [
                "bazel",
                "run",
                f"{secrets_package_full_path}:tf",
                "import",
                tf_resource,
            ]
            if tf_resource not in tf_resources:
                try:
                    secret_value = os.environ[env_var_name]
                    import_command.append(secret_value)
                    exit_code, _, _ = run_command(import_command)
                except KeyError as e:
                    logger.info(f"{env_var_name} is not set using prompt")
                    secret_value = input(f"Enter secret for {tf_resource}: ")
                    import_command.append(secret_value)
                    exit_code, _, _ = run_command(import_command)

                if exit_code != 0:
                    logger.error(f"Import secrets failed for {tf_resource}")
                    return False

                if final_apply:
                    final_apply_needed = True

    if final_apply_needed:
        exit_code, _, _ = run_command(
            ["bazel", "run", f"{secrets_package_full_path}:apply"]
        )
        if exit_code != 0:
            logger.error(f"Final {secrets_package_full_path}:apply failed")
            return False

    return True
