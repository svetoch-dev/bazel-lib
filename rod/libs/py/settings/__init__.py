from pydantic_settings import BaseSettings
from pydantic import Field, computed_field


class YcSettings(BaseSettings):
    tf_state_sa: str = "tf-state"
    caller: str = Field(
        validation_alias="USER",
        default="not identified",
    )


class LogSettings(BaseSettings):
    log_level: str = "INFO"


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

    @computed_field
    @property
    # Relative to workspace root
    def tf_dir(self) -> str:
        if self.tf_dir_override:
            return self.tf_dir_override
        return f"terraform"

    @computed_field
    @property
    def tf_env_dir(self) -> str:
        if self.tf_env_dir_override:
            return self.tf_env_dir_override
        return f"{self.tf_dir}/environments"

    @computed_field
    @property
    def tf_product_dir(self) -> str:
        if self.tf_product_dir_override:
            return self.tf_product_dir_override
        return f"{self.tf_env_dir}/product"

    @computed_field
    @property
    # We assume that terraform.tfvars.json can be found
    # in the root of every project
    def tfvars_file(self) -> str:
        return f"{self.workspace}/terraform.tfvars.json"

    @computed_field
    @property
    # Relative to workspace root
    def rc_cloud(self) -> str:
        if self.rc_cloud_override:
            return self.rc_cloud_override
        return f"{self.workspace}/.bazelrc.cloud"

    @computed_field
    @property
    # Relative to workspace root
    def rc_cloud_yc(self) -> str:
        if self.rc_cloud_yc_override:
            return self.rc_cloud_yc_override
        return f"{self.workspace}/.bazelrc.cloud.yc"

    @computed_field
    @property
    # Relative to workspace root
    def rc_cloud_gcp(self) -> str:
        if self.rc_cloud_gcp_override:
            return self.rc_cloud_gcp_override
        return f"{self.workspace}/.bazelrc.cloud.gcp"


log_settings = LogSettings()
bazel_settings = BazelSettings()
