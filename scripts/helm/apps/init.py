from git import Repo
from libs.py.helpers import run_command
from libs.py.helpers.exceptions import CommandException
import os
import sys
import click

REPO_PATH = os.environ["BUILD_WORKSPACE_DIRECTORY"]
HELM_EXECUTABLE = os.environ["HELM_EXECUTABLE"]
APP_CHART_PATH_DEFAULT = f"{REPO_PATH}/argocd/charts/app"


def init_submodules(repo):
    """Initialize and update submodules."""
    repo.submodule_update(init=True, recursive=True)


@click.command()
@click.argument("app_name", required=True, type=click.STRING)
@click.option("--app_chart_path", default=APP_CHART_PATH_DEFAULT, required=False)
def main(app_name, app_chart_path):
    repo = Repo(REPO_PATH)

    init_submodules(repo)

    chart_path = f"{app_chart_path}/{app_name}"

    if os.path.exists(chart_path):
        try:
            run_command(
                [HELM_EXECUTABLE, "dependency", "update", "hui"], raise_exception=True
            )
        except CommandException as e:
            sys.exit(e.args[0])
    else:
        print("Path does not exist")
        sys.exit(1)

    print("success")


if __name__ == "__main__":
    main()
