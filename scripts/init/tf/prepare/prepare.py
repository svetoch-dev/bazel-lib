from libs.py.tf.tfvars import formatted_tfvars
from scripts.init.tf.prepare.gcp import prepare_gcp
from scripts.init.tf.prepare.yc import prepare_yc
import sys


def prepare() -> None:
    """
    Prepares various clouds for applying terraform root modules
    """
    tfvars = formatted_tfvars()
    for env_name, env_obj in tfvars.envs.items():
        if env_obj.cloud.name == "gcp":
            prepared = prepare_gcp(env_obj.cloud.id)
            if not prepared:
                sys.exit(1)
        elif env_obj.cloud.name == "yc":
            prepared = prepare_yc()
            if not prepared:
                sys.exit(1)
        else:
            raise NotImplementedError(f"No prepare scripts for {env_obj.cloud.name}")


if __name__ == "__main__":
    prepare()
