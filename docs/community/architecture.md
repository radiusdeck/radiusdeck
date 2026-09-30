# RadiusDeck architecture

RadiusDeck owns the application process, the Community UI, and the core
FreeRADIUS configuration use cases. Separately installed packages may add
behavior through the neutral extension interface.

## Request and write flow

```text
HTTP request
  -> FastAPI router
  -> service use case
  -> repository and parser
  -> atomic clients.conf save
  -> optional reload port
  -> HTML response
```

Routers translate HTTP input and errors. Services contain use-case rules and do
not depend on FastAPI types. Repositories own asynchronous file access, locking,
and persistence. Mappers translate between parser nodes and typed request or UI
models.

Every configuration mutation acquires the per-file asynchronous lock, loads the
latest document, validates the proposed tree, writes a recovery backup, saves
the result, and invokes the reload port. Service results include both the
primary result and reload outcome so the HTTP layer can display a warning when
reload fails.

## Package layout

- `radiusdeck.main` builds the FastAPI application and owns its lifespan.
- `radiusdeck.web` contains HTML routes and HTTP dependencies.
- `radiusdeck.services` contains application use cases and neutral ports.
- `radiusdeck.repositories` contains configuration, backup, user, and log I/O.
- `radiusdeck.lib.fr_parser` contains tokenizer, AST, parser, merge, and renderer.
- `radiusdeck.mappers` translates between AST and typed application models.
- `radiusdeck.integrations` implements optional external-service ports.
- `radiusdeck.extensions` defines discovery, contributions, and lifecycle.

## Application construction

`create_app()` discovers installed entry points, validates their extension API
version, collects structural contributions, and then constructs routes and
middleware. During lifespan startup it creates the base services, starts
extension runtime hooks in deterministic order, and records their runtime state.
Shutdown runs started hooks in reverse order.

The module-level `radiusdeck.main:app` remains compatible with ASGI servers and
the `radiusdeck serve` command.

## Authentication and route policy

Open and local authentication are built in. Each route has a registered access
policy: public browser, protected browser, or protected programmatic route.
Authentication providers contributed by an extension participate only in
policies that name them. Duplicate or ambiguous route policies stop application
construction.

Session authentication sets the current user before route protection runs.
Unsafe cookie-authenticated requests use CSRF validation. Authentication
providers can return authenticated, rejected, or not-applicable results without
coupling middleware to a concrete provider implementation.

## Parser and editing contract

The parser represents assignments, nested blocks, comments, and blank lines as
an AST. Tree editing uses stable node identifiers. Missing identifiers delete
existing nodes; new nodes use a null identifier. Merge keeps the order and
comments of nodes that remain. Numeric values render without quotes unless the
input explicitly contains quotes.

## Backups and logs

Community creates a backup immediately before a successful configuration write
and supports confirmed rollback to the latest backup. Startup prepares backup
storage before extensions run so an extension cannot accidentally prune
external history.

The basic log service reads a bounded tail asynchronously and redacts common
secret forms before returning text to the UI. It accepts only the configured
log path.

## Deployment boundary

The production container is built from the independently tested Community
wheel. It runs as UID/GID `10001`, contains no repository checkout, and exposes
port 8000. A reload sidecar is optional and is reached through a typed port; a
disabled deployment uses the null implementation.

See [extensions.md](../extensions.md) for the public extension contract.
