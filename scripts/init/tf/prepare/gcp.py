from libs.py.gcp.api import enable_apis


def prepare_gcp(project_id: str) -> bool:
    apis = ["compute.googleapis.com"]

    return enable_apis(project_id, apis)
