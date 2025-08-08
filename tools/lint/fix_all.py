import subprocess
import os
from libs.py.helpers import run_command

WORKSPACE_FOLDER = os.getenv("BUILD_WORKSPACE_DIRECTORY")


def main():
    """
    Fix lint for all languages

    This is done
    1. by executing bazel command and query all targets with name `lint_fix`
    2. executing all those targets via `bazel run`
    """
    os.chdir(WORKSPACE_FOLDER)
    command = [
        "bazel",
        "query",
        'attr(name, "^(lint_fix_py|lint_fix_tf|lint_fix_bzl)$", "//...")',
    ]
    return_code, output = run_command(command, print_stdout=False)
    for target in output:
        command = ["bazel", "run", target]
        run_command(command)


if __name__ == "__main__":
    main()
