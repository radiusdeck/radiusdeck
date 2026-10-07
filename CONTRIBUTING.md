# Contributing to RadiusDeck

Thank you for helping improve RadiusDeck. This guide describes the development
workflow and the checks expected for a pull request.

## Before you start

- Read and follow the [Code of Conduct](.github/CODE_OF_CONDUCT.md).
- Search existing issues and pull requests before opening a new one.
- Open an issue before starting a large feature or architectural change so its
  scope can be agreed on first.
- Report vulnerabilities privately by following [SECURITY.md](SECURITY.md).

## Development setup

RadiusDeck requires Python 3.12 or newer.

```bash
git clone https://github.com/radiusdeck/radiusdeck.git
cd radiusdeck
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt -r requirements-dev.txt -e .
```

Run the application with a disposable FreeRADIUS client configuration:

```bash
touch /tmp/radiusdeck-clients.conf
APP_ENV=development \
APP_RADIUS_CLIENTS_PATH=/tmp/radiusdeck-clients.conf \
APP_BACKUP_DIR=/tmp/radiusdeck/backups \
radiusdeck serve
```

Do not use a production FreeRADIUS configuration for development or tests.

## Code guidelines

- Add type hints to all function arguments and return values.
- Use asynchronous file I/O with `aiofiles` and prefer `pathlib.Path`.
- Keep file access and locking in repositories, mapping in mappers, business
  behavior in services, and HTTP behavior in routers.
- Keep FastAPI types out of the service layer. Routers translate domain errors
  into HTTP responses.
- Protect configuration writes with the per-config asynchronous lock.
- Keep templates simple and put application logic in Python.
- Follow the existing extension interfaces instead of importing optional
  packages into the Community application.

## Tests and quality checks

Run the standard checks before submitting a pull request:

```bash
make lint
make test
make test-community-artifact
```

The artifact check builds and installs the wheel, verifies its contents, and
runs smoke tests against the installed package. Changes to the container build
should also pass:

```bash
make test-community-image
```

Use `tmp_path` for file-based tests. Mock reload integrations for service and
endpoint tests; tests must not read or modify a real FreeRADIUS configuration.

## Pull requests

- Keep each pull request focused on one change.
- Add or update tests for changed behavior.
- Update documentation when configuration or user-facing behavior changes.
- Use Conventional Commit messages, such as
  `feat: add FreeRADIUS status check` or `fix: preserve inline comments`.
- Ensure all required GitHub Actions checks pass.

By submitting a contribution, you agree that it may be distributed under the
terms of the [MIT License](LICENSE).
