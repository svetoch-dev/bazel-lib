from rod.libs.py.helpers import run_command


def in_state(tf_target: str, resource: str) -> bool:
    """
    Check whether a resource is present in a Terraform state.

    Runs ``bazel run <tf_target> state list`` and searches for the resource
    in the listed state entries.

    Args:
        tf_target: Bazel target that wraps the Terraform configuration.
        resource: Terraform resource address to look up in the state.

    Returns:
        True when the resource is found in the state, False otherwise.
    """
    state_list_command = ["bazel", "run", tf_target, "state", "list"]
    exit_code, stderr, tf_resources = run_command(
        state_list_command, print_stdout=False
    )
    return resource in tf_resources
