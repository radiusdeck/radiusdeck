from radiusdeck.services.ports import ReloadPort
from radiusdeck.services.reload_models import ReloadResult


class NullReloadClient(ReloadPort):
    """A reloader that does nothing, used when sidecar is disabled."""

    async def reload(self) -> ReloadResult:
        """Immediately returns a 'skipped' result without I/O."""
        return ReloadResult.skipped()
