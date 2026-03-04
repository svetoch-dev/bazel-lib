from pathlib import Path
from libs.py.settings import bazel_settings
import shutil
import os


def prepare_repo():
    os.chdir(bazel_settings.workspace)
    gitpath = Path(".git")
    if gitpath.exists() and gitpath.is_dir():
        shutil.rmtree(gitpath)


if __name__ == "__main__":
    prepare_repo()
