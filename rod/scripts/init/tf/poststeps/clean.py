import os
import shutil
from rod.libs.py.settings import bazel_settings


def clean() -> None:
    os.chdir(bazel_settings.workspace)
    shutil.rmtree(bazel_settings.tf_product_dir)


if __name__ == "__main__":
    clean()
