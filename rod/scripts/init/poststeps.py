import os
import shutil
import sys
from rod.libs.py.settings import bazel_settings, init_settings


def clean() -> None:
    os.chdir(bazel_settings.workspace)
    shutil.rmtree("tests/e2e")


if __name__ == "__main__":
    if init_settings.test:
        sys.exit(0)

    clean()
