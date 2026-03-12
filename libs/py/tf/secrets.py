import os
from libs.py.helpers import run_command
from libs.py.tf.tfvars import ImportSecret
from libs.py.settings import bazel_settings
from libs.py.utils.logger import CliLogger, BaseLogger


def import_secrets(
    env: str,
    secrets: dict[str, ImportSecret],
    logger: BaseLogger = CliLogger("scripts.init.tf.secrets.secrets.import_secrets"),
) -> bool:
    os.chdir(bazel_settings.workspace)
    secrets_package = f"//{bazel_settings.tf_env_dir}/{env}/secrets"
    state_list_command = ["bazel", "run", f"{secrets_package}:tf", "state", "list"]
    exit_code, stderr, tf_resources = run_command(
        state_list_command, print_stdout=False
    )
    if exit_code != 0:
        logger.error(f"State list failed for {secrets_package}")
        return False

    final_apply_needed = False

    for secret_name, secret_obj in secrets.items():
        for secret_key in secret_obj.secrets_to_import:
            tf_resource = f'module.secrets.module.rod_secrets["{secret_name}"].module.import_secret["{secret_key}"].secret_resource.secret'
            import_command = [
                "bazel",
                "run",
                f"{secrets_package}:tf",
                "import",
                tf_resource,
            ]
            if tf_resource not in tf_resources:
                env_secret_name = secret_name.replace("-", "__")
                env_secret_key = secret_key.replace("-", "__")
                env_var_name = (
                    f"TF_IMPORT_SECRET_{env_secret_name}_{env_secret_key}".upper()
                )
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

                final_apply_needed = True

    if final_apply_needed:
        exit_code, _, _ = run_command(["bazel", "run", f"{secrets_package}:apply"])
        if exit_code != 0:
            logger.error(f"Final {secrets_package}:apply failed")
            return False

    return True
