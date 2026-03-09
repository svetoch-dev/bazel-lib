from scripts.init.tf.state.gcs import create_gcs_tf_state
from scripts.init.tf.state.ycs3 import create_yc_s3_tf_state
from libs.py.tf.tfvars import formatted_tfvars
import sys


def create_state():
    """
    Create tf state backends for each env
    """

    tfvars = formatted_tfvars()
    for env_name, env_obj in tfvars.envs.items():
        if env_obj.tf_backend.type == "gcs":
            created = create_gcs_tf_state(
                env_obj.cloud.id,
                env_obj.tf_backend.configs["bucket"],
                env_obj.cloud.region,
            )
            if not created:
                sys.exit(1)
        elif env_obj.cloud.name == "yc" and env_obj.tf_backend.type == "s3":
            created = create_yc_s3_tf_state()
            if not created:
                sys.exit(1)
        else:
            raise NotImplementedError(
                f"No tf_state scripts for {env_obj.tf_backend.type}"
            )


if __name__ == "__main__":
    create_state()
