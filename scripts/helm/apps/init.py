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

    if os.path.exists(app_chart_path):
        charts = []
        failure_count = 0
        if app_name == "all":
            for file_name in os.listdir(app_chart_path):
                file_name = f"{app_chart_path}/{file_name}"
                if os.path.isdir(file_name):
                    charts.append(file_name)
        else:
            charts.append(f"{app_chart_path}/{app_name}")

        for chart in charts:
            try:
                run_command(
                    [HELM_EXECUTABLE, "dependency", "update", chart],
                    raise_exception=True,
                )
            except CommandException as e:
                failure_count += 1

        if failure_count > 0:
            sys.exit(1)
    else:
        print(f"{app_chart_path} path does not exist")
        sys.exit(1)


if __name__ == "__main__":
    main()
