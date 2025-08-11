from git import Repo
from libs.py.helpers import run_command
import os
import click

REPO_PATH = os.environ["BUILD_WORKSPACE_DIRECTORY"]
HELM_EXECUTABLE = os.environ["HELM_EXECUTABLE"]
APP_CHART_PATH_DEFAULT = f"{REPO_PATH}/argocd/charts/app"


def init_submodules(repo):
    """Initialize and update submodules."""
    repo.submodule_update(init=True, recursive=True)


def helm_app_init(chart_path):
    run_command([HELM_EXECUTABLE, "dependency", "update", chart_path])


@click.command()
@click.argument("app_name", required=True, type=click.STRING)
@click.option("--app_chart_path", default=APP_CHART_PATH_DEFAULT, required=False)
def main(app_name, app_chart_path):
    repo = Repo(REPO_PATH)

    init_submodules(repo)

    print(f"{app_chart_path}/{app_name}")

    print("success")


if __name__ == "__main__":
    main()
