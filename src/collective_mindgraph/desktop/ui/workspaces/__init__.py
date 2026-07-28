"""Six product workspaces used by the desktop shell."""

from .capture import CaptureWorkspace
from .dashboard import DashboardWorkspace
from .knowledge import KnowledgeWorkspace
from .meetings import MeetingsWorkspace
from .memory import MemoryWorkspace
from .settings import SettingsWorkspace

__all__ = [
    "CaptureWorkspace",
    "DashboardWorkspace",
    "KnowledgeWorkspace",
    "MeetingsWorkspace",
    "MemoryWorkspace",
    "SettingsWorkspace",
]
