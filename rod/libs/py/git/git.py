from git import Repo


def init_submodules(repo_path: str):
    """Initialize and update submodules."""
    repo = Repo(repo_path)
    repo.submodule_update(init=True, recursive=True)
