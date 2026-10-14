from abc import ABC, abstractmethod

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings


class YcSettings(BaseSettings):
    tf_state_sa: str = "tf-state"
    caller: str = Field(
        validation_alias="USER",
        default="not identified",
    )


class K8sClusterSettings(ABC):
    @property
    @abstractmethod
    def endpoint(self) -> str:
        """Https url of K8s cluster"""
        ...

    @property
    @abstractmethod
    def ca_cert(self) -> str:
        """Base64 encoded k8s cluster ca cert"""
        ...


class AWSSettings(BaseSettings):
    s3_endpoint: str = Field(
        validation_alias="AWS_ENDPOINT_URL_S3", default="https://s3.amazonaws.com"
    )


class LogSettings(BaseSettings):
    log_level: str = "INFO"


class InitSettings(BaseSettings):
    test: bool = Field(
        validation_alias="ROD_INIT_TEST",
        default=False,
    )


class BazelSettings(BaseSettings):
    workspace: str = Field(
        validation_alias="BUILD_WORKSPACE_DIRECTORY",
        default=".",
    )

    tf_dir_override: str | None = None
    tf_env_dir_override: str | None = None
    tf_product_dir_override: str | None = None

    rc_cloud_yc_override: str | None = None
    rc_cloud_gcp_override: str | None = None
    rc_cloud_override: str | None = None

    argocd_dir_override: str | None = None
    argocd_chart_dir_override: str | None = None
    argocd_app_chart_dir_override: str | None = None
    argocd_crds_dir_override: str | None = None

    deps_dir_override: str | None = None
    deps_images_dir_override: str | None = None

    @computed_field
    @property
    def deps_dir(self) -> str:
        if self.deps_dir_override:
            return f"{self.workspace}/{self.deps_dir_override}"
        return f"{self.workspace}/deps"

    @computed_field
    @property
    def deps_images_dir(self) -> str:
        if self.deps_images_dir_override:
            return f"{self.deps_dir}/{self.deps_images_dir_override}"
        return f"{self.deps_dir}/images"

    @computed_field
    @property
    def argocd_dir(self) -> str:
        if self.argocd_dir_override:
            return f"{self.workspace}/{self.argocd_dir_override}"
        return f"{self.workspace}/argocd"

    @computed_field
    @property
    def argocd_chart_dir(self) -> str:
        if self.argocd_chart_dir_override:
            return f"{self.argocd_dir}/{self.argocd_chart_dir_override}"
        return f"{self.argocd_dir}/charts/infra/charts"

    @computed_field
    @property
    def argocd_app_chart_dir(self) -> str:
        if self.argocd_app_chart_dir_override:
            return f"{self.argocd_dir}/{self.argocd_app_chart_dir_override}"
        return f"{self.argocd_dir}/charts/app"

    @computed_field
    @property
    def argocd_crds_dir(self) -> str:
        if self.argocd_crds_dir_override:
            return f"{self.argocd_dir}/{self.argocd_crds_dir_override}"
        return f"{self.argocd_dir}/charts/infra/crds"

    @computed_field
    @property
    def tf_dir(self) -> str:
        if self.tf_dir_override:
            return f"{self.workspace}/{self.tf_dir_override}"
        return f"{self.workspace}/terraform"

    @computed_field
    @property
    def tf_env_dir(self) -> str:
        if self.tf_env_dir_override:
            return f"{self.tf_dir}/{self.tf_env_dir_override}"
        return f"{self.tf_dir}/environments"

    @computed_field
    @property
    def tf_product_dir(self) -> str:
        if self.tf_product_dir_override:
            return f"{self.tf_dir}/{self.tf_product_dir_override}"
        return f"{self.tf_env_dir}/product"

    @computed_field
    @property
    # We assume that terraform.tfvars.json can be found
    # in the root of every project
    def tfvars_file(self) -> str:
        return f"{self.workspace}/terraform.tfvars.json"

    @computed_field
    @property
    def rc_cloud(self) -> str:
        if self.rc_cloud_override:
            return f"{self.workspace}/{self.rc_cloud_override}"
        return f"{self.workspace}/.bazelrc.cloud"

    @computed_field
    @property
    def rc_cloud_yc(self) -> str:
        if self.rc_cloud_yc_override:
            return f"{self.workspace}/{self.rc_cloud_yc_override}"
        return f"{self.workspace}/.bazelrc.cloud.yc"

    @computed_field
    @property
    def rc_cloud_gcp(self) -> str:
        if self.rc_cloud_gcp_override:
            return f"{self.workspace}/{self.rc_cloud_gcp_override}"
        return f"{self.workspace}/.bazelrc.cloud.gcp"


log_settings = LogSettings()
bazel_settings = BazelSettings()
init_settings = InitSettings()
