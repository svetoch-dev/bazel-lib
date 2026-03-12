import os
import shutil
from libs.py.settings import bazel_settings


def clean() -> None:
    os.chdir(bazel_settings.workspace)
    shutil.rmtree('tests/e2e')


if __name__ == "__main__":
    clean()
