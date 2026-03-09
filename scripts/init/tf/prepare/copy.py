from shutil import copytree
from libs.py.tf.tfvars import formatted_tfvars


def copy_template() -> None:
    tfvars = formatted_tfvars()


if __name__ == "__main__":
    copy_template()
