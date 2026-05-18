import os
import json
from typing import Any
from pathlib import Path
from rod.libs.py.settings import bazel_settings
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.tf.output import tf_output_registries

OUTPUT_FILE = os.environ["TF_OUTPUT_FILE"]
ENV_NAME = os.environ["TF_ENV_NAME"]


def update_tfvars():
    tfvars = formatted_tfvars()
    with open(OUTPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    registries = tf_output_registries(data)
    for env_name, env_obj in tfvars.envs.items():
        if env_name == ENV_NAME:
            env_obj.registry.url = registries["containers"]["endpoint"]

    Path(bazel_settings.tfvars_file).write_text(
        tfvars.model_dump_json(indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    update_tfvars()
