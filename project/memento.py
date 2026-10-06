from dataclasses import dataclass
from datetime import datetime


# ------------------------------------------------------- memento --
@dataclass(frozen=True)
class DocumentMemento:
    """A read-only snapshot of one version of a Document (the originator)."""
    version: int
    original_filename: str
    stored_filename: str
    filesize_bytes: int
    uploaded_at: datetime
