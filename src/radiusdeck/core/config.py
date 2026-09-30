import warnings
from pathlib import Path
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AuthMethod = str
SameSite = Literal["lax", "strict", "none"]
Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    # Main variables
    RADIUS_CLIENTS_PATH: Path = Path("clients3.conf")
    PROJECT_NAME: str = "My Radius App"

    env: Environment = "production"
    environment: Environment | None = Field(default=None, exclude=True, repr=False)

    LOG_LEVEL: str = "DEBUG"  # DEBUG/INFO/WARNING/ERROR
    LOG_FORMAT: str = "console"  # console | json

    # ── FreeRADIUS log viewer ───────────────────────────
    freeradius_log_viewer_enabled: bool = False
    freeradius_log_path: Path = Path("/var/log/freeradius/radius.log")
    freeradius_log_default_lines: int = 200
    freeradius_log_max_bytes: int = 512_000

    # -- clients.conf backups -----------------------------
    backup_enabled: bool = True
    backup_dir: Path = Path("/data/backups/clients")

    # ── Auth ─────────────────────────────────────────────
    # Built-in providers: none | local; extensions register other identifiers.
    auth_method: AuthMethod = "none"

    # Required when auth_method == "local"
    local_users_path: Path | None = None

    public_url: AnyHttpUrl | None = None

    # ── Session (Epic B) ─────────────────────────────────
    # Required when auth_method != "none"
    session_secret_key: SecretStr | None = None
    session_max_age_seconds: int = Field(default=86400, ge=1)
    session_idle_timeout_seconds: int = Field(default=86400, ge=0)
    secure_cookies: bool | None = None
    session_cookie_name: str = "radiusdeck_session"
    session_samesite: SameSite = "lax"

    # ── CSRF (Epic E) ────────────────────────────────────
    csrf_header_name: str = "X-CSRF-Token"
    csrf_form_field_name: str = "csrf_token"

    REQUEST_ID_HEADER: str = "X-Request-ID"

    # ── Sidecar reload ───────────────────────────────────
    SIDECAR_RELOAD_ENABLED: bool = False
    SIDECAR_RELOAD_URL: AnyHttpUrl | None = None
    SIDECAR_HEALTH_URL: AnyHttpUrl | None = None
    SIDECAR_RELOAD_TOKEN: SecretStr | None = None
    SIDECAR_RELOAD_TIMEOUT_SECONDS: float = 10

    @field_validator("auth_method", mode="before")
    @classmethod
    def _normalize_auth_method(cls, v: object) -> object:
        if v is None:
            return "none"
        if isinstance(v, str):
            normalized = v.strip().lower()
            return normalized or "none"
        return v

    @model_validator(mode="before")
    @classmethod
    def _migrate_environment_alias(cls, value: object) -> object:
        if not isinstance(value, dict):
            return value

        alias = value.get("environment")
        if alias is None:
            return value

        migrated = dict(value)
        current = migrated.get("env")
        if current is None:
            migrated["env"] = alias
            warning = (
                "APP_ENVIRONMENT is deprecated; use APP_ENV. " f"Using APP_ENV={alias}."
            )
        else:
            warning = "APP_ENVIRONMENT is deprecated; APP_ENV takes precedence."
            if current != alias:
                warning += (
                    f" Conflicting values were provided (APP_ENV={current}, "
                    f"APP_ENVIRONMENT={alias})."
                )
        warnings.warn(warning, DeprecationWarning, stacklevel=2)
        return migrated

    @model_validator(mode="after")
    def _validate_session_secret_key_required(self) -> "Settings":
        if self.auth_method != "none" and self.session_secret_key is None:
            raise ValueError(
                "APP_SESSION_SECRET_KEY is required when authentication is enabled"
            )
        return self

    @model_validator(mode="after")
    def _validate_local_users_path_required(self) -> "Settings":
        if self.auth_method == "local" and self.local_users_path is None:
            raise ValueError(
                "APP_LOCAL_USERS_PATH is required when APP_AUTH_METHOD is 'local'"
            )
        return self

    @model_validator(mode="after")
    def _validate_backup_path(self) -> "Settings":
        backup_path = self.backup_dir.expanduser().resolve(strict=False)
        clients_path = self.RADIUS_CLIENTS_PATH.expanduser().resolve(strict=False)
        if backup_path == clients_path:
            raise ValueError("APP_BACKUP_DIR must not equal APP_RADIUS_CLIENTS_PATH")
        return self

    @property
    def csrf_enabled(self) -> bool:
        return self.auth_method != "none"

    @property
    def effective_secure_cookies(self) -> bool:
        if self.secure_cookies is not None:
            return self.secure_cookies
        if self.public_url is None:
            return False
        return str(self.public_url).lower().startswith("https://")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        env_prefix="APP_",
        extra="ignore",
    )


settings = Settings()
