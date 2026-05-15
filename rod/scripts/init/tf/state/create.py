from rod.libs.py.tf.state import create_gcs_tf_state
from rod.libs.py.tf.state import create_yc_s3_tf_state
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.settings import AWSSettings, YcSettings
from rod.libs.py.yc.sa import YcServiceAccount
from types import SimpleNamespace
import sys


def create_state() -> None:
    """Create Terraform state backends for all configured environments.

    For Yandex Object Storage backends, also initialize the secrets state object
    derived from the configured backend key template.
    """
    tfvars = formatted_tfvars()
    aws_settings = AWSSettings()
    int_env = next(
        env_obj
        for env_name, env_obj in tfvars.envs.items()
        if env_obj.type == "internal"
    )
    for env_name, env_obj in tfvars.envs.items():
        if env_obj.tf_backend.type == "gcs":
            created = create_gcs_tf_state(
                env_obj.cloud.id,
                env_obj.tf_backend.configs["bucket"],
                env_obj.cloud.location.region,
            )
            if not created:
                sys.exit(1)
        elif (
            aws_settings.s3_endpoint == "https://storage.yandexcloud.net"
            and env_obj.tf_backend.type == "s3"
        ):
            yc_settings = YcSettings()
            tf_backend = SimpleNamespace(state_name="secrets")
            secrets_state = env_obj.tf_backend.configs["key"].format(
                tf_backend=tf_backend
            )
            service_account = YcServiceAccount(
                int_env.cloud.folder_id,
                yc_settings.tf_state_sa,
            )
            created = create_yc_s3_tf_state(
                env_obj.cloud.folder_id,
                env_obj.tf_backend.configs["bucket"],
                service_account.id,
                secrets_state,
            )
            if not created:
                sys.exit(1)
        else:
            raise NotImplementedError(
                f"No tf_state scripts for {env_obj.tf_backend.type}"
            )


if __name__ == "__main__":
    create_state()
