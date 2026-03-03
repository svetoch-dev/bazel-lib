from pydantic_settings import BaseSettings
from pydantic import Field, computed_field


class LogSettings(BaseSettings):
    log_level: str = "INFO"


class BazelSettings(BaseSettings):
    workspace: str = Field(
        validation_alias="BUILD_WORKSPACE_DIRECTORY",
        default=".",
    )

    @computed_field
    @property
    # We assume that terraform.tfvars.json can be found
    # in the root of every project
    def tfvars(self) -> str:
        return f"{self.workspace}/terraform.tfvars.json"


log_settings = LogSettings()
bazel_settings = BazelSettings()
