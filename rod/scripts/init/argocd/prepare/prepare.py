from rod.libs.py.utils.logger import CliLogger


def prepare_argocd():
    logger = CliLogger("rod.scripts.init.argocd.prepare.update_kube_config")
    logger.info("Hello")


if __name__ == "__main__":
    prepare_argocd()
