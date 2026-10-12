import yaml

from rod.libs.py.k8s.client import kube_config_factory, KubeConfig
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.utils.logger import CliLogger
from pathlib import Path


def update_kube_config():
    logger = CliLogger("rod.libs.py.tf.poststeps.update_kube_config")
    tfvars = formatted_tfvars()

    kube_folder = Path("~/.kube").expanduser()
    kube_config_path = kube_folder / "config"
    kube_config = KubeConfig()

    if kube_folder.is_dir() and kube_config_path.is_file():
        with kube_config_path.open("r") as f:
            data = yaml.safe_load(f)

        kube_config = KubeConfig(**data)

    logger.info(f"Adding kuberenetes clusters to {str(kube_config_path)}")
    for env_obj in tfvars.envs.values():
        env_config = kube_config_factory(
            env_obj, company_name=tfvars.company.name, use_exec=True
        )
        for ctx in env_config.contexts:
            if ctx not in kube_config.contexts:
                kube_config.contexts.append(ctx)

        for user in env_config.users:
            if user not in kube_config.users:
                kube_config.users.append(user)

        for cluster in env_config.clusters:
            if cluster not in kube_config.clusters:
                kube_config.clusters.append(cluster)

    with kube_config_path.open("w") as f:
        yaml.safe_dump(kube_config.model_dump(), f, sort_keys=False)


if __name__ == "__main__":
    update_kube_config()
