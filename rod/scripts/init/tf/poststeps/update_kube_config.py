import yaml

from pathlib import Path

from rod.libs.py.k8s.client import kube_config_factory, KubeConfig, k8s_client_get
from rod.libs.py.k8s.exceptions import K8sClusterNotFound, K8sClusterPermissionsDenied
from rod.libs.py.tf.tfvars import formatted_tfvars
from rod.libs.py.utils.logger import CliLogger
from rod.libs.py.helpers import create_dir


def update_kube_config():
    logger = CliLogger("rod.scripts.init.tf.poststeps.update_kube_config")
    tfvars = formatted_tfvars()

    kube_folder = Path("~/.kube").expanduser()
    kube_config_path = kube_folder / "config"
    kube_config = KubeConfig()

    if kube_folder.is_dir() and kube_config_path.is_file():
        with kube_config_path.open("r") as f:
            data = yaml.safe_load(f)

        kube_config = KubeConfig(**data)
    else:
        create_dir(str(kube_folder))

    logger.info(f"Adding kuberenetes clusters to {str(kube_config_path)}")
    for env_obj in tfvars.envs.values():
        try:
            env_config = kube_config_factory(
                env_obj, company_name=tfvars.company.name, use_exec=True
            )
        except (K8sClusterNotFound, K8sClusterPermissionsDenied) as e:
            logger.error(str(e))
            continue

        for ctx in env_config.contexts:
            if ctx not in kube_config.contexts:
                kube_config.contexts.append(ctx)

        for user in env_config.users:
            if user not in kube_config.users:
                kube_config.users.append(user)

        for cluster in env_config.clusters:
            if cluster not in kube_config.clusters:
                kube_config.clusters.append(cluster)
        kube_config.current_context = env_config.current_context

        logger.info(f"Done for {env_obj.short_name}")

    with kube_config_path.open("w") as f:
        yaml.safe_dump(kube_config.model_dump(), f, sort_keys=False)


if __name__ == "__main__":
    update_kube_config()
