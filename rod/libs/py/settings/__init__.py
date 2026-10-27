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


class CommonPaths(BaseSettings):
    """
    Resolve filesystem paths used by infrastructure initialization.

    Paths are derived from the workspace and their parent directories.
    Overrides are relative to the parent documented for each setting.

    Args:
        workspace: Workspace root, read from BUILD_WORKSPACE_DIRECTORY.
            Defaults to the current directory.
        tf_dir_override: Terraform directory relative to the workspace.
        tf_env_dir_override: Environment directory relative to the Terraform directory.
        tf_product_dir_override: Product template relative to the Terraform directory.
        rc_cloud_yc_override: Yandex Cloud Bazel rc path relative to the workspace.
        rc_cloud_gcp_override: GCP Bazel rc path relative to the workspace.
        rc_cloud_override: Active cloud Bazel rc path relative to the workspace.
        argocd_dir_override: Argo CD directory relative to the workspace.
        argocd_environments_dir_override: Environment templates relative to Argo CD.
        argocd_internal_template_dir_override: Internal template directory relative
            to the Argo CD environments directory.
        argocd_product_template_dir_override: Product template directory relative
            to the Argo CD environments directory.
        argocd_chart_dir_override: Infrastructure charts relative to Argo CD.
        argocd_app_chart_dir_override: Application chart relative to Argo CD.
        argocd_crds_dir_override: CRD manifests relative to Argo CD.
        deps_dir_override: Dependency directory relative to the workspace.
        deps_images_dir_override: Image dependencies relative to the dependency directory.
    """

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
    argocd_environments_dir_override: str | None = None
    argocd_internal_template_dir_override: str | None = None
    argocd_product_template_dir_override: str | None = None
    argocd_chart_dir_override: str | None = None
    argocd_app_chart_dir_override: str | None = None
    argocd_crds_dir_override: str | None = None

    deps_dir_override: str | None = None
    deps_images_dir_override: str | None = None

    @computed_field
    @property
    def deps_dir(self) -> str:
        """
        Resolve the dependency directory path.

        Defaults to "deps" under the workspace. An override is
        resolved relative to the workspace.

        Returns:
            Filesystem path to the dependency directory.
        """
        if self.deps_dir_override:
            return f"{self.workspace}/{self.deps_dir_override}"
        return f"{self.workspace}/deps"

    @computed_field
    @property
    def deps_images_dir(self) -> str:
        """
        Resolve the image dependency directory path.

        Defaults to "images" under the dependency directory. An override is
        resolved relative to the dependency directory.

        Returns:
            Filesystem path to the image dependency directory.
        """
        if self.deps_images_dir_override:
            return f"{self.deps_dir}/{self.deps_images_dir_override}"
        return f"{self.deps_dir}/images"

    @computed_field
    @property
    def argocd_dir(self) -> str:
        """
        Resolve the Argo CD directory path.

        Defaults to "argocd" under the workspace. An override is
        resolved relative to the workspace.

        Returns:
            Filesystem path to the Argo CD directory.
        """
        if self.argocd_dir_override:
            return f"{self.workspace}/{self.argocd_dir_override}"
        return f"{self.workspace}/argocd"

    @computed_field
    @property
    def argocd_environments_dir(self) -> str:
        """
        Resolve the Argo CD environment template directory path.

        Defaults to "environments" under the Argo CD directory. An override is
        resolved relative to the Argo CD directory.

        Returns:
            Filesystem path to the Argo CD environment template directory.
        """
        if self.argocd_environments_dir_override:
            return f"{self.argocd_dir}/{self.argocd_environments_dir_override}"
        return f"{self.argocd_dir}/environments"

    @computed_field
    @property
    def argocd_internal_template_dir(self) -> str:
        """
        Resolve the Argo CD internal environment template directory path.

        Defaults to "int" under the Argo CD environments directory. An override is
        resolved relative to the Argo CD environments directory.

        Returns:
            Filesystem path to the Argo CD internal template directory.
        """
        if self.argocd_internal_template_dir_override:
            return f"{self.argocd_environments_dir}/{self.argocd_internal_template_dir_override}"
        return f"{self.argocd_environments_dir}/int"

    @computed_field
    @property
    def argocd_product_template_dir(self) -> str:
        """
        Resolve the Argo CD product environment template directory path.

        Defaults to "product" under the Argo CD environments directory. An override is
        resolved relative to the Argo CD environments directory.

        Returns:
            Filesystem path to the Argo CD product template directory.
        """
        if self.argocd_product_template_dir_override:
            return f"{self.argocd_environments_dir}/{self.argocd_product_template_dir_override}"
        return f"{self.argocd_environments_dir}/product"

    @computed_field
    @property
    def argocd_chart_dir(self) -> str:
        """
        Resolve the infrastructure chart directory path.

        Defaults to "charts/infra/charts" under the Argo CD directory. An override is
        resolved relative to the Argo CD directory.

        Returns:
            Filesystem path to the infrastructure chart directory.
        """
        if self.argocd_chart_dir_override:
            return f"{self.argocd_dir}/{self.argocd_chart_dir_override}"
        return f"{self.argocd_dir}/charts/infra/charts"

    @computed_field
    @property
    def argocd_app_chart_dir(self) -> str:
        """
        Resolve the application chart directory path.

        Defaults to "charts/app" under the Argo CD directory. An override is
        resolved relative to the Argo CD directory.

        Returns:
            Filesystem path to the application chart directory.
        """
        if self.argocd_app_chart_dir_override:
            return f"{self.argocd_dir}/{self.argocd_app_chart_dir_override}"
        return f"{self.argocd_dir}/charts/app"

    @computed_field
    @property
    def argocd_crds_dir(self) -> str:
        """
        Resolve the CRD manifest directory path.

        Defaults to "charts/infra/crds" under the Argo CD directory. An override is
        resolved relative to the Argo CD directory.

        Returns:
            Filesystem path to the CRD manifest directory.
        """
        if self.argocd_crds_dir_override:
            return f"{self.argocd_dir}/{self.argocd_crds_dir_override}"
        return f"{self.argocd_dir}/charts/infra/crds"

    @computed_field
    @property
    def tf_dir(self) -> str:
        """
        Resolve the Terraform directory path.

        Defaults to "terraform" under the workspace. An override is
        resolved relative to the workspace.

        Returns:
            Filesystem path to the Terraform directory.
        """
        if self.tf_dir_override:
            return f"{self.workspace}/{self.tf_dir_override}"
        return f"{self.workspace}/terraform"

    @computed_field
    @property
    def tf_env_dir(self) -> str:
        """
        Resolve the Terraform environment directory path.

        Defaults to "environments" under the Terraform directory. An override is
        resolved relative to the Terraform directory.

        Returns:
            Filesystem path to the Terraform environment directory.
        """
        if self.tf_env_dir_override:
            return f"{self.tf_dir}/{self.tf_env_dir_override}"
        return f"{self.tf_dir}/environments"

    @computed_field
    @property
    def tf_product_dir(self) -> str:
        """
        Resolve the Terraform product template directory path.

        Defaults to "product" under the Terraform environment directory. An override is
        resolved relative to the Terraform directory.

        Returns:
            Filesystem path to the Terraform product template directory.
        """
        if self.tf_product_dir_override:
            return f"{self.tf_dir}/{self.tf_product_dir_override}"
        return f"{self.tf_env_dir}/product"

    @computed_field
    @property
    # We assume that terraform.tfvars.json can be found
    # in the root of every project
    def tfvars_file(self) -> str:
        """
        Resolve the Terraform variables file in the workspace root.

        Returns:
            Filesystem path to terraform.tfvars.json in the workspace.
        """
        return f"{self.workspace}/terraform.tfvars.json"

    @computed_field
    @property
    def rc_cloud(self) -> str:
        """
        Resolve the active cloud Bazel rc file path.

        Defaults to ".bazelrc.cloud" under the workspace. An override is
        resolved relative to the workspace.

        Returns:
            Filesystem path to the active cloud Bazel rc file.
        """
        if self.rc_cloud_override:
            return f"{self.workspace}/{self.rc_cloud_override}"
        return f"{self.workspace}/.bazelrc.cloud"

    @computed_field
    @property
    def rc_cloud_yc(self) -> str:
        """
        Resolve the Yandex Cloud Bazel rc file path.

        Defaults to ".bazelrc.cloud.yc" under the workspace. An override is
        resolved relative to the workspace.

        Returns:
            Filesystem path to the Yandex Cloud Bazel rc file.
        """
        if self.rc_cloud_yc_override:
            return f"{self.workspace}/{self.rc_cloud_yc_override}"
        return f"{self.workspace}/.bazelrc.cloud.yc"

    @computed_field
    @property
    def rc_cloud_gcp(self) -> str:
        """
        Resolve the GCP Bazel rc file path.

        Defaults to ".bazelrc.cloud.gcp" under the workspace. An override is
        resolved relative to the workspace.

        Returns:
            Filesystem path to the GCP Bazel rc file.
        """
        if self.rc_cloud_gcp_override:
            return f"{self.workspace}/{self.rc_cloud_gcp_override}"
        return f"{self.workspace}/.bazelrc.cloud.gcp"


class BazelSettings(BaseSettings):
    workspace: str = Field(
        validation_alias="BUILD_WORKSPACE_DIRECTORY",
        default=".",
    )

    tf_dir_override: str | None = None
    tf_env_dir_override: str | None = None
    deps_dir_override: str | None = None
    deps_images_dir_override: str | None = None

    @computed_field
    @property
    # Relative to workspace root
    def tf_dir(self) -> str:
        if self.tf_dir_override:
            return self.tf_dir_override
        return "terraform"

    @computed_field
    @property
    def tf_env_dir(self) -> str:
        if self.tf_env_dir_override:
            return f"{self.tf_dir}/{self.tf_env_dir_override}"
        return f"{self.tf_dir}/environments"

    @computed_field
    @property
    def deps_dir(self) -> str:
        """
        Resolve the dependency directory path.

        Defaults to "deps". An override is
        resolved relative to the workspace.

        Returns:
            bazel path to the dependency directory.
        """
        if self.deps_dir_override:
            return self.deps_dir_override
        return "deps"

    @computed_field
    @property
    def deps_images_dir(self) -> str:
        """
        Resolve the image dependency directory path.

        Defaults to "images" under the dependency directory. An override is
        resolved relative to the dependency directory.

        Returns:
            bazel path to the image dependency directory.
        """
        if self.deps_images_dir_override:
            return f"{self.deps_dir}/{self.deps_images_dir_override}"
        return f"{self.deps_dir}/images"


common_paths = CommonPaths()
log_settings = LogSettings()
bazel_settings = BazelSettings()
init_settings = InitSettings()
