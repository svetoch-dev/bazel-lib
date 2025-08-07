import subprocess
import os
from libs.py.helpers import run_command

WORKSPACE_FOLDER = os.getenv("BUILD_WORKSPACE_DIRECTORY")


def process_results(result):
    if result.returncode == 0:
        return result.stdout
    else:
        error = f"Bazel query failed with return code: {result.returncode}\n"
        error += "Error:\n"
        error += result.stderr

        raise BaseException(error)


def main():
    """
    Fix lint for all languages

    This is done
    1. by executing bazel command and query all targets with name `lint_fix`
    2. executing all those targets via `bazel run`
    """
    os.chdir(WORKSPACE_FOLDER)
    query = [
        "bazel",
        "query",
        'attr(name, "^(lint_fix_py|lint_fix_tf|lint_fix_bzl)$", "//...")',
    ]
    result = subprocess.run(query, capture_output=True, text=True)
    output = process_results(result)
    output = output.strip("\n")
    print(output)
    for target in output.split("\n"):
        command = ["bazel", "run", target]
        run_command(command)


if __name__ == "__main__":
    main()
