import os
import shutil
import sys
from pathlib import Path
from rod.libs.py.settings import common_paths, init_settings


def clean() -> None:
    os.chdir(common_paths.workspace)
    shutil.rmtree("tests/e2e")
    shutil.rmtree(common_paths.tf_product_dir)

    gitpath = Path(".git")
    if gitpath.exists() and gitpath.is_dir():
        shutil.rmtree(gitpath)


if __name__ == "__main__":
    if init_settings.test:
        sys.exit(0)

    clean()
