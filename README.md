# RadiusDeck

RadiusDeck is a lightweight web interface for managing FreeRADIUS text
configuration. It edits `clients.conf` through a parser that preserves comments,
blank lines, ordering, and nested blocks.

## Included capabilities

- list, create, edit, and delete FreeRADIUS clients;
- automatic backups before configuration changes and rollback to the latest backup;
- safe basic log viewing with secret redaction;
- reload and runtime diagnostics for an optional sidecar;
- open or local authentication;
- a neutral extension interface for separately installed Python packages.

## Requirements

- Python 3.12 or newer;
- a readable and writable `clients.conf`;
- optional access to a FreeRADIUS log file;
- optional access to a reload sidecar.

## Local installation

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install .
APP_ENV=development \
APP_RADIUS_CLIENTS_PATH=/path/to/clients.conf \
APP_BACKUP_DIR=/tmp/radiusdeck/backups \
radiusdeck serve
```

The server listens on `0.0.0.0:8000` by default. Use `--host` and `--port` to
override those values.

## Container build

The Dockerfile installs a tested wheel instead of copying the repository into
the image:

```bash
make test-community-artifact
docker compose build
docker compose up -d
```

Set `HOST_RADIUS_CLIENTS_CONF` to the absolute host path before starting the
Compose stack. The container runs as UID and GID `10001` and therefore needs
permission to read and update the mounted configuration and backup volume.
For HTTPS deployment, follow the certificate and reverse-proxy instructions in
[`deploy/certs/README.md`](deploy/certs/README.md).

## Configuration

Environment variables use the `APP_` prefix. Common settings are:

| Variable | Purpose | Default |
| --- | --- | --- |
| `APP_RADIUS_CLIENTS_PATH` | FreeRADIUS client configuration | `clients3.conf` |
| `APP_BACKUP_ENABLED` | Create recovery backups | `true` |
| `APP_BACKUP_DIR` | Backup directory | `/data/backups/clients` |
| `APP_AUTH_METHOD` | `none` or `local` | `none` |
| `APP_LOCAL_USERS_PATH` | Local user file | unset |
| `APP_SESSION_SECRET_KEY` | Session signing secret | unset |
| `APP_FREERADIUS_LOG_VIEWER_ENABLED` | Enable basic log view | `false` |
| `APP_FREERADIUS_LOG_PATH` | FreeRADIUS log file | `/var/log/freeradius/radius.log` |
| `APP_SIDECAR_RELOAD_ENABLED` | Call reload sidecar after writes | `false` |
| `APP_SIDECAR_RELOAD_URL` | Reload endpoint | unset |
| `APP_SIDECAR_RELOAD_TOKEN` | Reload bearer token | unset |

Local authentication requires both `APP_LOCAL_USERS_PATH` and
`APP_SESSION_SECRET_KEY`. Secure cookies are selected from `APP_PUBLIC_URL` and
can be overridden with `APP_SECURE_COOKIES`.

## Development checks

```bash
pytest tests
ruff check .
black --check .
mypy .
make test-community-artifact
make test-community-image
```

See [architecture](docs/community/architecture.md),
[backups](docs/community/backups.md), and the
[extension interface](docs/extensions.md) for the main runtime contracts.
