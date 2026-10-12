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


# ------------------------------------------------------- caretaker --
class VersionHistory:
    """Keeps the mementos of each document; never changes what is inside them."""
    def __init__(self, db, version_model):
        self.db = db
        self.version_model = version_model

    def save(self, document):
        memento = document.create_memento()
        self.db.session.add(self.version_model(
            document_id=document.id,
            version=memento.version,
            original_filename=memento.original_filename,
            stored_filename=memento.stored_filename,
            filesize_bytes=memento.filesize_bytes,
            uploaded_at=memento.uploaded_at,
        ))
        return memento

    def get_history(self, document):
        return [v.to_memento() for v in document.history]

    def get(self, document, version):
        saved = self.version_model.query.filter_by(document_id=document.id, version=version).first()
        return saved.to_memento() if saved else None
