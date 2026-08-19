from rod.libs.py.helpers import run_command


def in_state(tf_target: str, resource: str) -> bool:
    state_list_command = ["bazel", "run", tf_target, "state", "list"]
    exit_code, stderr, tf_resources = run_command(
        state_list_command, print_stdout=False
    )
    return resource in tf_resources
