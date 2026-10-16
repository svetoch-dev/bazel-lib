from rod.libs.py.git.git import init_submodules
from rod.libs.py.settings import bazel_settings
from rod.libs.py.utils.logger import CliLogger


def git_init_submodules():
    """
    Initialize and recursively update submodules in the Bazel workspace.

    Logs the operation and uses the configured workspace as the repository path.
    """
    logger = CliLogger("rod.scripts.init.argocd.prepare.init_submodules")
    logger.info("Init git submodules")
    init_submodules(bazel_settings.workspace)


if __name__ == "__main__":
    git_init_submodules()
