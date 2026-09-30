# clients.conf Backups

RadiusDeck can keep private, database-free recovery points for `clients.conf`.
Automatic backups are enabled by default and are created only before effective
create, update, and delete operations.

## Configuration

```text
APP_BACKUP_ENABLED=true
APP_BACKUP_DIR=/backups
APP_BACKUP_RETENTION_COUNT=100
APP_BACKUP_MAX_AGE_DAYS=30
```

`APP_BACKUP_MAX_AGE_DAYS` is optional. Count and age retention are applied after
each successful backup. Set `APP_BACKUP_ENABLED=false` to disable backup and
rollback features while keeping client editing available.

Use a dedicated persistent volume. The application creates the configured
directory with mode `0700` and backup files with mode `0600` where supported.
The container user must be able to create and replace files in that directory.

## Mutation Semantics

For an effective client change RadiusDeck reads the exact live file, builds and
validates the proposed AST, creates a recovery backup, writes the proposed
configuration, and triggers the configured reload integration.

- Backup failure: live file unchanged, reload not called.
- Save failure: recovery backup remains available.
- Reload failure: changed file and recovery backup remain available.
- No-op: no backup, no write, skipped reload.

## Rollback Semantics

Rollback is admin-only and requires the selected opaque backup ID to be repeated
as confirmation. RadiusDeck verifies the stored SHA-256 and parses the selected
content before touching the live file. It then creates a safety backup of the
current live file, restores exact selected content, verifies the restored hash,
and calls reload.

A reload failure does not undo a successful restore. The API/UI reports the
failure and links to the safety backup so an administrator can recover the state
that existed immediately before rollback.

## Sensitive Content

Backups contain RADIUS shared secrets. UI diffs replace `secret` assignment
values with `<redacted>`, but downloads intentionally return exact content.
Protect backup volumes, downloads, host-level snapshots, and transport paths as
sensitive configuration data. Backup files are not exposed by the application
static-file mount.
