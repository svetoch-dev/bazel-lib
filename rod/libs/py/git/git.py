from git import Repo


def init_submodules(repo_path: str):
    """
    Initialize and recursively update a repository's submodules.

    Args:
        repo_path: Path to the Git repository whose submodules should be updated.
    """
    repo = Repo(repo_path)
    repo.submodule_update(init=True, recursive=True)
