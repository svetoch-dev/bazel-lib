from libs.py.helpers.exceptions import CommandException
from libs.py.utils.logger import CliLogger
import subprocess
import glob
import re
import sys
import json

MASK_STR = "##MASKED##"
UNMASK_STR = ""


def unmask_tf(folder, mask_str=MASK_STR, unmask_str=UNMASK_STR):
    """
    Remove mask string from tf files of a bazel target

    Args:
        folder(str): folder with .tf files
        mask_str(str): string that should be unmasked
        unmask_str(str): unmasked str
    """
    tf_files = glob.glob(f"{folder}/*.tf")
    for file in tf_files:
        with open(file, "r") as f:
            content = f.read()

        content = re.sub(mask_str, unmask_str, content)

        with open(file, "w") as f:
            f.write(content)


def run_command(command, print_stdout=True, print_stderr=True, raise_exception=False):
    """
    Runs a command and captures its stdout and stderr.

    Args:
        command (list): A list of strings representing the command and its arguments.
        print_stdout (bool): If True, prints the command's stdout to the console.
        print_stderr (bool): If True, prints the command's stderr to the console.
        raise_exception (bool): If True, raises a CommandException on a non-zero return code.

    Returns:
        tuple: A tuple containing the return code, a list of stderr lines, and a list of stdout lines.
    """
    command_str = " ".join(command)
    stdout = []
    stderr = []
    logger = CliLogger("helpers.run_command")
    logger.debug(f"Running: {command_str}")
    result = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    for line in result.stdout:
        stdout.append(line.strip())
        if print_stdout:
            print(line, end="", file=sys.stdout)

    for line in result.stderr:
        stderr.append(line.strip())
        if print_stderr:
            print(line, end="", file=sys.stderr)

    result.wait()
    if result.returncode != 0:
        logger.debug(f"Command failed with return code: {result.returncode}")
        if raise_exception:
            raise CommandException(result.returncode, "\n".join(stderr))

    return result.returncode, stderr, stdout


def dict_to_dot_notation(
    dictionary: dict[str, object], initial_key: str = ""
) -> dict[str, object]:
    """Flatten a nested dictionary into a single-level dictionary
    using dot-separated keys.

    For example:
        {"test": {"a": 1, "b": 2}}
    becomes:
        {"test.a": 1, "test.b": 2}

    Args:
        dictionary: A potentially nested dictionary to flatten.
        initial_key: Optional prefix to prepend to all generated keys.
                     Used internally for recursive calls.

    Returns:
        A new dictionary where nested keys are represented
        in dot notation.
    """

    results = {}

    for key, value in dictionary.items():

        if initial_key:
            results_key = f"{initial_key}.{key}"
        else:
            results_key = key

        if isinstance(value, dict):
            results = results | dict_to_dot_notation(value, results_key)
        else:
            results[results_key] = value

    return results


def replace_dotted_placeholders(
    dictionary: dict[str, object], dot_notation_dict: dict[str, str]
) -> dict[str, object]:
    """
    Replace placeholders like "{key}" in a dictionary using values
    from a dot-notation dictionary.

    If a placeholder matches a key in `dot_notation_dict`, it is
    replaced with its corresponding value. Unmatched placeholders
    remain unchanged.

    Args:
        dictionary: Dictionary that may contain "{key}" placeholders.
        dot_notation_dict: Mapping of dot-notation keys to replacement values.

    Returns:
        A new dictionary with placeholders replaced.
    """

    json_str = json.dumps(dictionary)

    pattern = re.compile(r"\{([a-zA-z0-9.]+)\}")

    def replace(match):
        key = match.group(1)
        if key in dot_notation_dict:
            return str(dot_notation_dict[key])
        return match.group(0)

    json_str = pattern.sub(replace, json_str)

    return json.loads(json_str)
