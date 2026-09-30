from pathlib import Path

import pytest
from pydantic import ValidationError

from radiusdeck.core.config import Settings


def test_backup_settings_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_BACKUP_ENABLED", "false")
    monkeypatch.setenv("APP_BACKUP_DIR", "/tmp/radiusdeck-backups")
    monkeypatch.setenv("APP_BACKUP_RETENTION_COUNT", "25")
    monkeypatch.setenv("APP_BACKUP_MAX_AGE_DAYS", "30")

    settings = Settings(_env_file=None)

    assert settings.backup_enabled is False
    assert settings.backup_dir == Path("/tmp/radiusdeck-backups")
    assert "backup_retention_count" not in Settings.model_fields
    assert "backup_max_age_days" not in Settings.model_fields


def test_backup_directory_must_not_equal_live_config(tmp_path: Path) -> None:
    path = tmp_path / "clients.conf"
    with pytest.raises(ValidationError, match="APP_BACKUP_DIR"):
        Settings(_env_file=None, RADIUS_CLIENTS_PATH=path, backup_dir=path)
