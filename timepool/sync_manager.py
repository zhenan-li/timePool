from .i18n import tr


class SyncManager:
    """Reserved extension point for future multi-device sync."""

    def status_text(self) -> str:
        return tr("Sync: not available")

    def sync(self) -> str:
        return self.status_text()
