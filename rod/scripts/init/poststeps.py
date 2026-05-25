import os
import shutil
import sys
from rod.libs.py.settings import bazel_settings, init_settings


def clean() -> None:
    os.chdir(bazel_settings.workspace)
    shutil.rmtree("tests/e2e")
    shutil.rmtree(bazel_settings.tf_product_dir)

    gitpath = Path(".git")
    if gitpath.exists() and gitpath.is_dir():
        shutil.rmtree(gitpath)


if __name__ == "__main__":
    if init_settings.test:
        sys.exit(0)

    clean()
