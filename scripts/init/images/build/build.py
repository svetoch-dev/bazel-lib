import os
from libs.py.helpers import run_command
from libs.py.settings import bazel_settings


def build_images() -> None:
    """
    Build and push custom images to container registries

    This is done
    1. by executing bazel command and query all targets starting with `push_` in all subpackages of deps/images
    2. executing all those target via `bazel run`
    """
    os.chdir(bazel_settings.workspace)
    query = ["bazel", "query", 'attr(name, "^push_.*$", "//deps/images/...")']
    return_code, stderr, stdout = run_command(
        query, print_stdout=True, print_stderr=True
    )
    for target in stdout:
        command = ["bazel", "run", target]
        run_command(command)


if __name__ == "__main__":
    build_images()
