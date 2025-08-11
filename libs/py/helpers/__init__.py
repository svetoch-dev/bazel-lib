from libs.py.helpers.exceptions import CommandException
import subprocess
import glob
import re

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
    command_str = " ".join(command)
    stdout = []
    stderr = []
    print(f"Running: {command_str}")
    result = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    for line in result.stdout:
        stdout.append(line.strip())
        if print_stdout:
            print(line, end="")

    for line in result.stderr:
        stderr.append(line.strip())
        if print_stderr:
            print(line, end="")

    result.wait()
    if result.returncode != 0:
        print("Command failed with return code:", result.returncode)
        if raise_exception:
            raise CommandException(result.returncode, "\n".join(stderr))

    return result.returncode, stderr, stdout
