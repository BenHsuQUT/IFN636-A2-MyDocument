from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

from project.memento import DocumentMemento

db = SQLAlchemy()


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")  # 'user' | 'admin'
    is_active_account = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    documents = db.relationship(
        "Document", backref="owner", lazy=True, cascade="all, delete-orphan"
    )
    categories = db.relationship(
        "Category", backref="owner", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def initial(self):
        return (self.username or "?")[0].upper()

    def total_storage_bytes(self):
        return sum(d.total_size_bytes() for d in self.documents)

    def latest_documents(self):
        return (
            Document.query.filter_by(user_id=self.id)
            .order_by(Document.uploaded_at.desc())
            .all()
        )


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(80), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_id", "name", name="uq_category_user_name"),)


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    version = db.Column(db.Integer, nullable=False, default=1)

    title = db.Column(db.String(150), nullable=False)
    category = db.Column(db.String(80), nullable=True, default="Uncategorized")
    notes = db.Column(db.Text, nullable=True)

    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    filesize_bytes = db.Column(db.Integer, nullable=False, default=0)

    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

    # previous versions saved by the caretaker, newest first
    history = db.relationship(
        "DocumentVersion", backref="document", lazy=True, cascade="all, delete-orphan",
        order_by="DocumentVersion.version.desc()",
    )

    # ------------------------------------------- originator (memento pattern) --
    def create_memento(self):
        return DocumentMemento(
            version=self.version,
            original_filename=self.original_filename,
            stored_filename=self.stored_filename,
            filesize_bytes=self.filesize_bytes,
            uploaded_at=self.uploaded_at,
            uploaded_by=self.owner.username,
        )

    def restore_from_memento(self, memento):
        # the restored file becomes a new version, so no existing version is overwritten
        self.version += 1
        self.original_filename = memento.original_filename
        self.stored_filename = memento.stored_filename
        self.filesize_bytes = memento.filesize_bytes
        self.uploaded_at = datetime.utcnow()

    def total_size_bytes(self):
        return self.filesize_bytes + sum(v.filesize_bytes for v in self.history)

    def relative_path(self):
        return f"{self.user_id}/{self.stored_filename}"

    def d_size(self):
        size = float(self.filesize_bytes)
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024:
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def extension(self):
        return self.original_filename.rsplit(".", 1)[-1].lower() if "." in self.original_filename else ""

    def icon_label(self):
        ext = self.extension()
        return {
            "docx": "W", "doc": "W",
            "pdf": "PDF",
            "txt": "TXT"
        }.get(ext, ext.upper()[:3] or "FILE")

    def is_previewable_image(self):
        pass

    def is_previewable_pdf(self):
        pass

    def is_recent(self, days=7):
        return self.uploaded_at and self.uploaded_at >= datetime.utcnow() - timedelta(days=days)


class DocumentVersion(db.Model):
    """Database storage for the mementos of a document (its previous versions)."""
    __tablename__ = "document_versions"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)

    version = db.Column(db.Integer, nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    filesize_bytes = db.Column(db.Integer, nullable=False, default=0)
    uploaded_at = db.Column(db.DateTime, nullable=False)

    __table_args__ = (db.UniqueConstraint("document_id", "version", name="uq_document_version"),)

    def to_memento(self):
        return DocumentMemento(
            version=self.version,
            original_filename=self.original_filename,
            stored_filename=self.stored_filename,
            filesize_bytes=self.filesize_bytes,
            uploaded_at=self.uploaded_at,
            # only the owner can upload versions, so the owner is the uploader
            uploaded_by=self.document.owner.username,
        )
