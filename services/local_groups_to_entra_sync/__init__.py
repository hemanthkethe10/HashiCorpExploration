# local_groups_to_entra_sync service package

from .orchestrator import SyncOrchestrator
from .schemas import SyncSummaryResponse

SyncSummary = SyncSummaryResponse  # backwards-compat alias

__all__ = ["SyncOrchestrator", "SyncSummary", "SyncSummaryResponse"]
