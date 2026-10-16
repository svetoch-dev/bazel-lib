from pathlib import Path

import yaml

from kubernetes import client, utils

from rod.libs.py.k8s.client import k8s_client_get
from rod.libs.py.tf.tfvars import Env
from rod.libs.py.utils.logger import CliLogger, BaseLogger
from rod.libs.py.helpers import get_folder_files
from rod.libs.py.k8s.exceptions import K8sApiException


def apply_yaml_file(
    api_client: client.ApiClient,
    yaml_file: str | Path,
    # default namespace is the default for namespace attr
    # in create_from_yaml. Treat it as not set
    namespace: str | None = "default",
):
    """
    Deserialize and apply the Kubernetes objects in a YAML file.

    Skips empty YAML documents. Each document's metadata.namespace overrides
    the fallback namespace supplied by the caller.

    Args:
        api_client: Kubernetes API client used to apply the objects.
        yaml_file: Path to a file containing one or more YAML documents.
        namespace: Fallback namespace for documents without metadata.namespace.

    Raises:
        utils.FailToCreateError: The Kubernetes client cannot apply an object.
    """
    with open(yaml_file, encoding="utf-8") as f:
        for obj in yaml.safe_load_all(f):
            if obj is None:
                continue
            object_namespace = obj.get("metadata", {}).get("namespace", namespace)
            utils.create_from_yaml(
                api_client,
                yaml_objects=[obj],
                apply=True,
                namespace=object_namespace,
            )


def apply_manifests(
    env: Env,
    # default namespace is the default for namespace attr
    # in create_from_yaml. Treat it as not set
    namespace: str | None = "default",
    dir_path: str | None = None,
    file_path: str | None = None,
    logger: BaseLogger | None = None,
):
    """
    Apply Kubernetes manifests from a YAML file or directory.

    Directory inputs include only immediate entries ending in ".yaml" or
    ".yml". Each YAML document uses its declared namespace when present.

    Args:
        env: Environment identifying the target Kubernetes cluster.
        namespace: Fallback namespace for documents without metadata.namespace.
        dir_path: Directory containing YAML manifests. Mutually exclusive with
            file_path.
        file_path: YAML manifest file to apply. Mutually exclusive with dir_path.
        logger: Logger to use, or None to create a CLI logger.

    Raises:
        ValueError: Neither or both of dir_path and file_path are supplied.
        FileNotFoundError: The manifest directory or file does not exist.
        K8sApiException: The Kubernetes client cannot apply a manifest.
    """
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
                apply_yaml_file(client.client, file, namespace=namespace)
            except utils.FailToCreateError as e:
                raise K8sApiException(e)
    elif file_path:
        try:
            apply_yaml_file(client.client, file_path, namespace=namespace)
        except utils.FailToCreateError as e:
            raise K8sApiException(e)
