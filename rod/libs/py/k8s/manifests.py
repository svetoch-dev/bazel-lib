import json

from kubernetes import utils

from rod.libs.py.k8s.client import k8s_client_get
from rod.libs.py.tf.tfvars import Env
from rod.libs.py.utils.logger import CliLogger, BaseLogger
from rod.libs.py.helpers import get_folder_files
from rod.libs.py.k8s.exceptions import K8sApiException


def apply_manifests(
    env: Env,
    namespace: str | None = "default",
    dir_path: str | None = None,
    file_path: str | None = None,
    logger: BaseLogger | None = None,
):
    logger = logger or CliLogger("rod.libs.py.k8s.manifests.apply_manifests")

    kwargs = {
        "dir_path": dir_path,
        "file_path": file_path,
    }
    set_attrs = [(k, v) for k, v in kwargs.items() if v is not None]
    if len(set_attrs) != 1:
        raise ValueError(f"One and only one of {','.join(kwargs.keys())} should be set")

    client = k8s_client_get(env)

    if dir_path:
        files = get_folder_files(dir_path, extensions=[".yaml", ".yml"])
        for file in files:
            try:
                utils.create_from_yaml(
                    client.client, yaml_file=file, apply=True, namespace=namespace
                )
            except utils.FailToCreateError as e:
                raise K8sApiException(e)
    elif file_path:
        try:
            utils.create_from_yaml(
                client.client, yaml_file=file_path, apply=True, namespace=namespace
            )
        except utils.FailToCreateError as e:
            raise K8sApiException(e)
