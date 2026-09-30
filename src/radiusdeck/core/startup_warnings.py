from __future__ import annotations

from radiusdeck.core.config import Settings

_DEV_SECRET_FRAGMENTS: tuple[str, ...] = (
    "changeme",
    "change-me",
    "dev-session-secret",
    "replace-with",
    "test-secret",
)


def is_development_secret(value: str) -> bool:
    normalized = value.lower()
    return any(fragment in normalized for fragment in _DEV_SECRET_FRAGMENTS)


def get_startup_warnings(settings: Settings) -> list[str]:
    warnings: list[str] = []

    if settings.auth_method == "none":
        warnings.append("APP_AUTH_METHOD=none. Do not expose this instance publicly.")

    public_url = str(settings.public_url) if settings.public_url is not None else None
    if settings.auth_method != "none" and (
        public_url is None or not public_url.lower().startswith("https://")
    ):
        warnings.append(
            "APP_AUTH_METHOD is enabled but APP_PUBLIC_URL does not use https://."
        )

    if settings.session_secret_key is not None:
        secret = settings.session_secret_key.get_secret_value().lower()
        if is_development_secret(secret):
            warnings.append(
                "APP_SESSION_SECRET_KEY appears to use a development/default value."
            )

    if (
        public_url is not None
        and public_url.lower().startswith("https://")
        and not settings.effective_secure_cookies
    ):
        warnings.append(
            "Secure cookies are disabled while APP_PUBLIC_URL uses https://."
        )

    return warnings
