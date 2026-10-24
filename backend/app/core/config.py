"""MVP configuration; never loads a .env file implicitly."""
from pathlib import Path
from typing import Literal
from pydantic import ValidationError
from pydantic_settings import SettingsError
from pydantic import Field, HttpUrl, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=None, extra="ignore", hide_input_in_errors=True)
    environment: Literal["development", "test", "production"] = Field(
        default="development", validation_alias="MARLIN_ENVIRONMENT")
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", validation_alias="MARLIN_LOG_LEVEL")
    rhino_compute_url: HttpUrl | None = Field(
        default=None, validation_alias="RHINO_COMPUTE_URL", repr=False)
    rhino_compute_api_key: SecretStr | None = Field(
        default=None, validation_alias="RHINO_COMPUTE_API_KEY", repr=False)
    rhino_compute_timeout: float = Field(
        default=10.0, gt=0, le=300, validation_alias="RHINO_COMPUTE_TIMEOUT", repr=False)
    rhino_compute_max_attempts: int = Field(
        default=3, ge=1, le=10, validation_alias="RHINO_COMPUTE_MAX_ATTEMPTS", repr=False)
    rhino_compute_backoff_seconds: float = Field(
        default=0.0, ge=0, le=60, validation_alias="RHINO_COMPUTE_BACKOFF_SECONDS", repr=False)
    # Server-side Grasshopper definition names/paths (COMPUTE /grasshopper "pointer").
    rhino_station_definition: str = Field(
        default="marlin_station_curves", validation_alias="RHINO_STATION_DEFINITION", repr=False)
    rhino_hull_definition: str = Field(
        default="marlin_hull", validation_alias="RHINO_HULL_DEFINITION", repr=False)
    rhino_box_definition: str = Field(
        default="marlin_box", validation_alias="RHINO_BOX_DEFINITION", repr=False)
    marlin_storage_dir: str = Field(
        default="storage", validation_alias="MARLIN_STORAGE_DIR", repr=False)

    @field_validator("rhino_compute_url", "rhino_compute_api_key", mode="before")
    @classmethod
    def blank_is_unset(cls, value):
        return None if value == "" else value


class ConfigurationError(ValueError):
    """Safe startup diagnostic with field names only, never supplied values."""


def load_settings(*, env_file: str | Path | None = None) -> Settings:
    if env_file is not None:
        path = Path(env_file)
        if not path.is_absolute() or not path.is_file():
            raise ConfigurationError("env_file must be an existing absolute file path")
    message = "Invalid MVP settings"
    try:
        return Settings(_env_file=env_file, _env_file_encoding="utf-8")
    except ValidationError as error:
        allowed = {"MARLIN_ENVIRONMENT", "MARLIN_LOG_LEVEL", "RHINO_COMPUTE_URL",
                   "RHINO_COMPUTE_API_KEY", "RHINO_COMPUTE_TIMEOUT",
                   "RHINO_COMPUTE_MAX_ATTEMPTS", "RHINO_COMPUTE_BACKOFF_SECONDS",
                   "RHINO_STATION_DEFINITION", "RHINO_HULL_DEFINITION", "RHINO_BOX_DEFINITION",
                   "MARLIN_STORAGE_DIR"}
        fields = sorted({str(e["loc"][0]) for e in error.errors(include_input=False)
                         if e["loc"] and e["loc"][0] in allowed})
        message += ": " + ", ".join(fields)
    except (SettingsError, OSError, UnicodeError):
        message = "Unable to read MVP settings"
    # Outside the except block: no raw exception chained into startup logs.
    raise ConfigurationError(message)

