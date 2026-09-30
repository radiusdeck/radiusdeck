# Manual backup checks

Use a disposable `clients.conf` and backup directory. Never run these checks
against an unmanaged production configuration.

## Setup

```bash
tmpdir=$(mktemp -d)
printf 'client local {\n ipaddr = 127.0.0.1\n secret = test\n}\n' > "$tmpdir/clients.conf"
APP_ENV=test \
APP_AUTH_METHOD=none \
APP_RADIUS_CLIENTS_PATH="$tmpdir/clients.conf" \
APP_BACKUP_DIR="$tmpdir/backups" \
radiusdeck serve --host 127.0.0.1 --port 8000
```

## Checks

1. Open `/ui/clients` and create a client.
2. Confirm that the client appears in `clients.conf` and one backup exists.
3. Edit the client and confirm that another pre-change backup exists.
4. Open `/ui/backups`, request rollback to the latest backup, and confirm it.
5. Verify that `clients.conf` contains the state from immediately before the
   last edit.
6. Make the backup directory unwritable and attempt another mutation. The
   configuration must remain unchanged and the UI must report the failure.
7. Restore permissions, repeat the mutation, and verify that reload failure is
   shown as a warning while the saved configuration remains valid.

Also verify that backup names cannot select files outside the configured backup
directory and that the backup directory is different from `clients.conf`.
