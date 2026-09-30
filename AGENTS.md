# AI Context & Instructions

This document provides context for AI assistants working on the RadiusDeck codebase.

## Project Overview
**RadiusDeck** is a modern web interface for managing FreeRADIUS servers.
It is designed to be lightweight, fast, and easy to deploy via Docker.
It can optionally integrate with a sidecar container to automatically reload the FreeRADIUS service after a configuration change.

## Tech Stack
- **Backend:** Python 3.12+, FastAPI, Uvicorn.
- **HTTP Client:** httpx for calling external services (like the reload sidecar).
- **Frontend:** Server-side rendered Jinja2 templates + HTMX for interactivity (no SPA frameworks)
- **Styling:** Bootstrap 5 (currently via CDN)
- **Database/Storage:** The application parses and writes directly to FreeRADIUS text config files (`clients.conf`). No SQL database is used for core logic.
- **Parsing:** Custom AST-based parser for FreeRADIUS config format (located in `src/radiusdeck/lib/fr_parser`).
- **Deployment:** Docker, with an optional docker-reload-sidecar container.

## Code Style & Conventions
- **Linting:** We use `ruff` for linting and `black` for formatting.
- **Type Hints:** All function arguments and return values MUST be typed. Use `mypy` in strict mode.
- **Imports:** Sorted by `isort` (profile "black").
- **Async:** All I/O operations (file reading/writing) MUST be asynchronous (`aiofiles`).

## Architecture & Boundaries
- **Repositories/Stores (`src/radiusdeck/repositories/`):** File I/O, locking, load/save of AST.
- **Integrations (`src/radiusdeck/integrations/`):** Communication with external services. Contains clients like `SidecarReloadClient`. These clients should implement a Port from the service layer.
- **Mappers (`src/radiusdeck/mappers/`):** AST ↔ DTO transformations for API/UI.
- **Services (`src/radiusdeck/services/`):** Business use-cases (list/get/upsert/delete clients). Services should not depend on FastAPI types. Services now orchestrate persistence (via Repositories) and triggering actions (via Integration Ports).
Mutating service methods (create, update, delete) MUST call the reloader port after a successful save.
They MUST return a combined result object (e.g., UpsertResult, DeleteResult) containing both the primary data and the ReloadResult.
- **Routers (`src/radiusdeck/web/`):** HTTP layer only; use `Depends()` for DI. Responsible for handling the combined result from the service layer and formatting the response (e.g., showing a warning if `reload_result.status == "failed"`).

### Error Handling
- Routers raise `HTTPException`.
- Service layer raises domain exceptions (or returns `None`) and must not raise `HTTPException`.

### Concurrency
- Writes must be protected with a per-config async lock (e.g. `ClientsConfStore.locked()`).

## Dependency Injection
- The `RadiusService` is created once in app lifespan/startup and stored in `app.state`.
- Access it via a dependency function (e.g. `get_radius_service(request)`).
- A ReloadPort implementation (SidecarReloadClient or NullReloadClient) is also created in the lifespan based on environment variables and injected into the RadiusService.

## Configuration (Environment Variables)
The application is configured via environment variables, prefixed with APP_.
- APP_RADIUS_CLIENTS_PATH: Path to the clients.conf file inside the container (e.g., /data/clients.conf).
- APP_SIDECAR_RELOAD_ENABLED: true or false. Enables or disables calling the reload sidecar. Defaults to false.
- APP_SIDECAR_RELOAD_URL: URL of the sidecar's /reload endpoint (e.g., http://reload-sidecar:9090/reload).
- APP_SIDECAR_RELOAD_TOKEN: Bearer token for authenticating with the sidecar.

## Testing
- Use `pytest`.
- Use `tmp_path` for temp configs and FastAPI `dependency_overrides` to inject a test service.
- Do not read/write real FreeRADIUS configs in tests.
- When testing services or endpoints that cause a reload, the ReloadPort dependency MUST be mocked. Use unittest.mock.AsyncMock and inject it into the test RadiusService instance.

## Commit Messages
- Use Conventional Commits format for commit messages, e.g. `feat: add FreeRADIUS log viewer`.


## Key Locations
- `src/radiusdeck/lib/fr_parser/`: tokenizer/parser/AST/renderer
- `src/radiusdeck/lib/fr_parser/merge.py`: AST merge logic for tree-based client editing
- `src/radiusdeck/repositories/clients_conf_store.py`: config file store (I/O + lock)
- `src/radiusdeck/services/radius_service.py`: business use-cases
- `src/radiusdeck/templates/`: Jinja2 templates
- `src/radiusdeck/services/reload_models.py`: Contains domain models for reload results (ReloadResult, ReloadStatus).
- `radiusdeck.services.ports`: Contains the ReloadPort interface.
- `src/radiusdeck/integrations/sidecar_reload_client.py`: Production implementation of ReloadPort.
- `src/radiusdeck/integrations/null_reload_client.py`: Null object implementation of ReloadPort.

## Tree-based Client Editing (UI) — Important Contracts

### Payload + node_id
- Tree edit uses stable `node_id` to map form nodes to AST nodes.
- Existing nodes use ids:
  - root extra assignments: `a:0`, `a:1`, ...
  - root blocks: `b:0`, `b:1`, ...
  - nested paths: `b:0/a:0`, `b:0/b:0/a:1`, etc.
- New nodes are sent with `"id": null`.
- Missing existing ids in payload implies deletion of that node (assignment or block).
- Root-level extra assignments must not use reserved keys `ipaddr`/`secret` (those are edited via dedicated fields).

### Merge rules
- Editing must merge into existing AST (do NOT replace whole block) to preserve:
  - `CommentLine`, `BlankLine`
  - assignment `inline_comment` (kept only if assignment kept; removed if assignment removed)
  - order of existing nodes
- Merge code lives in `src/radiusdeck/lib/fr_parser/merge.py` and is covered by unit tests.

### UI endpoints (web)
- Create:
  - `POST /ui/clients/add-tree` (payload_json)
- Edit (left panel):
  - `GET /ui/clients/{name}/edit-form`
  - `GET /ui/clients/create-form` (Cancel)
  - `PUT /ui/clients/{name}/tree` (payload_json)

### Clients table + OOB swap
- Each client is rendered as a separate `<tbody id="client-block-<name>">` containing 2 `<tr>` (row + details placeholder).
- Create appends new client `<tbody>` to `#clients-table`.
- Edit save returns create form HTML + an OOB `<tbody hx-swap-oob="outerHTML">` to refresh that client block.

### Quoting expectation
- Numeric values should be rendered without quotes unless user explicitly enters quotes.

## Instructions for AI
1. When generating code, always include type hints.
2. Prefer `pathlib.Path` over `os.path`.
3. When modifying parser logic, ensure existing tests in `tests/` do not break.
4. If suggesting a new library, check if it's already in `requirements.txt`.
5. Use `Depends()` for service injection, never import singletons
6. Keep templates simple — logic belongs in service/mapper, not in Jinja2
7. Follow existing patterns: check similar files before creating new ones
