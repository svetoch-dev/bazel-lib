from pydantic_settings import BaseSettings
from pydantic import Field, computed_field


class LogSettings(BaseSettings):
    log_level: str = "INFO"


class BazelSettings(BaseSettings):
    workspace: str | None = Field(
        validation_alias="BUILD_WORKSPACE_DIRECTORY",
        default=None,
    )


log_settings = LogSettings()
bazel_settings = BazelSettings()
