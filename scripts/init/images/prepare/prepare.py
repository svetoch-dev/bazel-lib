import os
import json

from libs.py.helpers import create_file
from libs.py.tf.tfvars import formatted_tfvars

HOME_DIR = os.getenv("HOME")
DOCKER_CONFIG_DIR = f"{HOME_DIR}/.docker"
DOCKER_CONFIG_FILE = f"{DOCKER_CONFIG_DIR}/config.json"


class CredsHelperNotImplemented(BaseException):
    pass


def create_cred_helpers():
    """
    creates a credHelpers section in ~/.docker/config.json based on registries
    if terraform.tfvars.json
    """
    create_file(DOCKER_CONFIG_FILE)
    tfvars = formatted_tfvars()

    registries = []

    for env_name, env_obj in tfvars.envs.items():

        if env_obj.cloud.name == "gcp":
            creds_helper = "gcloud"
        elif env_obj.cloud.name == "yc":
            creds_helper = "yc"
        else:
            raise CredsHelperNotImplemented(
                f"creds_helper not found for this registry {env_obj.cloud.registry}"
            )

        registries.append({"url": env_obj.cloud.registry, "creds_helper": creds_helper})

    configs = {"auths": {}, "credHelpers": {}}

    try:
        with open(DOCKER_CONFIG_FILE, "r") as f:
            configs = json.load(f)
    except json.JSONDecodeError:
        print(
            f"Error: The file '{DOCKER_CONFIG_FILE}' contains invalid JSON. Or is empty"
        )
        print("Using default configs")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    for registry in registries:
        registry_domain = registry["url"].split("/")[0]

        configs["credHelpers"][registry_domain] = registry["creds_helper"]

    with open(DOCKER_CONFIG_FILE, "w") as f:
        json.dump(configs, f, indent=4)


if __name__ == "__main__":
    create_cred_helpers()
