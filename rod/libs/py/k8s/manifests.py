from pathlib import Path

import yaml

from kubernetes import client, utils

from rod.libs.py.k8s.client import k8s_client_get
from rod.libs.py.tf.tfvars import Env
from rod.libs.py.utils.logger import CliLogger, BaseLogger
from rod.libs.py.helpers import get_folder_files
from rod.libs.py.k8s.exceptions import K8sApiException


def apply_object(
    api_client: client.ApiClient,
    obj: dict,
    # default namespace is the default for namespace attr
    # in create_from_yaml. Treat it as not set
    namespace: str | None = "default",
):
    """
    Apply a single deserialized Kubernetes object.

    The object's metadata.namespace overrides the fallback namespace supplied
    by the caller.

    Args:
        api_client: Kubernetes API client used to apply the object.
        obj: Deserialized Kubernetes object (one YAML or JSON document).
        namespace: Fallback namespace if the object has no metadata.namespace.

    Raises:
        utils.FailToCreateError: The Kubernetes client cannot apply the object.
    """
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
    yaml_object: dict | None = None,
    logger: BaseLogger | None = None,
):
    """
    Apply Kubernetes manifests from a YAML object, file, or directory.

    Directory inputs include only immediate entries ending in ".yaml" or
    ".yml". Each YAML document uses its declared namespace when present.

    For file and directory inputs, all documents are attempted even if some
    fail. Application failures are collected and raised together as a single
    K8sApiException after every document has been processed.

    Args:
        env: Environment identifying the target Kubernetes cluster.
        namespace: Fallback namespace for documents without metadata.namespace.
        dir_path: Directory containing YAML manifests. Mutually exclusive with
            file_path and yaml_object.
        file_path: YAML manifest file to apply. Mutually exclusive with
            dir_path and yaml_object.
        yaml_object: Deserialized Kubernetes object to apply directly.
            Mutually exclusive with dir_path and file_path.
        logger: Logger to use, or None to create a CLI logger.

    Raises:
        ValueError: Not exactly one of dir_path, file_path, and yaml_object
            is supplied.
        FileNotFoundError: The manifest directory or file does not exist.
        K8sApiException: One or more Kubernetes manifests failed to apply.
    """
    logger = logger or CliLogger("rod.libs.py.k8s.manifests.apply_manifests")

    kwargs = {
        "dir_path": dir_path,
        "file_path": file_path,
        "yaml_object": yaml_object,
    }
    set_attrs = [(k, v) for k, v in kwargs.items() if v is not None]
    if len(set_attrs) != 1:
        raise ValueError(f"One and only one of {','.join(kwargs.keys())} should be set")

    client = k8s_client_get(env)

    if yaml_object is not None:
        try:
            apply_object(client.client, yaml_object, namespace=namespace)
        except utils.FailToCreateError as e:
            raise K8sApiException(e) from e
    else:
        files = (
            get_folder_files(dir_path, extensions=[".yaml", ".yml"])
            if dir_path
            else [file_path]
        )
        exceptions = []
        for file in files:
            with open(file, encoding="utf-8") as f:
                for obj in yaml.safe_load_all(f):
                    if obj is None:
                        continue
                    try:
                        apply_object(client.client, obj, namespace=namespace)
                    except utils.FailToCreateError as e:
                        exceptions.append(e)
        if exceptions:
            raise K8sApiException(exceptions)
