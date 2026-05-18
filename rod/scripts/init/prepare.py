from pathlib import Path
from rod.libs.py.settings import bazel_settings, init_settings
import shutil
import os
import sys


def prepare_repo():
    os.chdir(bazel_settings.workspace)
    gitpath = Path(".git")
    if gitpath.exists() and gitpath.is_dir():
        shutil.rmtree(gitpath)


if __name__ == "__main__":
    if init_settings.test:
        sys.exit(0)

    prepare_repo()
