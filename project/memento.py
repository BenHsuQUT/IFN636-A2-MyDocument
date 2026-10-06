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
    uploaded_by: str

    def to_dict(self):
        # public fields only, the stored file name stays on the server
        return {
            "version": self.version,
            "original_filename": self.original_filename,
            "filesize_bytes": self.filesize_bytes,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "uploaded_by": self.uploaded_by,
        }
