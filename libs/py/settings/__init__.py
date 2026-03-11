from pydantic_settings import BaseSettings
from pydantic import Field, computed_field


class LogSettings(BaseSettings):
    log_level: str = "INFO"


class BazelSettings(BaseSettings):
    workspace: str = Field(
        validation_alias="BUILD_WORKSPACE_DIRECTORY",
        default=".",
    )

    tf_dir_override: str | None = None

    tf_env_dir_override: str | None = None
    tf_template_dir_override: str | None = None

    @computed_field
    @property
    # Relative to workspace root
    def tf_dir(self) -> str:
        if self.tf_dir_override:
            return tf_dir_override
        return f"terraform"

    @computed_field
    @property
    def tf_env_dir(self) -> str:
        if self.tf_env_dir_override:
            return tf_env_dir_override
        return f"{self.tf_dir}/environments"

    @computed_field
    @property
    def tf_template_dir(self) -> str:
        if self.tf_template_dir_override:
            return tf_template_dir_override
        return f"{self.tf_env_dir}/template"

    @computed_field
    @property
    # We assume that terraform.tfvars.json can be found
    # in the root of every project
    def tfvars_file(self) -> str:
        return f"{self.workspace}/terraform.tfvars.json"


log_settings = LogSettings()
bazel_settings = BazelSettings()
