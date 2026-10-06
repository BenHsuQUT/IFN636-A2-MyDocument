import os
import shutil
import uuid
from datetime import datetime, timedelta

from werkzeug.utils import secure_filename

from project.models import db, User, Document, DocumentVersion, Category, new_uuid
from project.utils import allowed_file


# ---------------------------- exceptions --
class ValidationError(Exception):
    def __init__(self, *messages):
        super().__init__(*messages)
        self.messages = list(messages)


class AccessDeniedError(Exception):
    pass


# ----------------------------- subsystem: file storage --
class FileStorage:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder

    def user_folder(self, user_id):
        return os.path.join(self.upload_folder, str(user_id))

    def save(self, user_id, file):
        ext = file.filename.rsplit(".", 1)[1].lower()
        folder = self.user_folder(user_id)
        os.makedirs(folder, exist_ok=True)
        stored_filename = f"{uuid.uuid4().hex}.{ext}"
        filepath = os.path.join(folder, stored_filename)
        file.save(filepath)
        return stored_filename, os.path.getsize(filepath)

    def delete(self, user_id, stored_filename):
        filepath = os.path.join(self.user_folder(user_id), stored_filename)
        if os.path.exists(filepath):
            os.remove(filepath)

    def delete_user_folder(self, user_id):
        folder = self.user_folder(user_id)
        if os.path.isdir(folder):
            shutil.rmtree(folder)


# ----------------------------- subsystem: version history (memento caretaker) --
class VersionHistory:
    def save(self, document):
        memento = document.create_memento()
        db.session.add(DocumentVersion(
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
        saved = DocumentVersion.query.filter_by(document_id=document.id, version=version).first()
        return saved.to_memento() if saved else None


# --------------------------------------------------- facade --
class MyDocumentFacade:
    def __init__(self, config):
        self.config = config
        self.storage = FileStorage(config["UPLOAD_FOLDER"])
        self.version_history = VersionHistory()

    # -------------------------------------- auth --
    def get_user(self, user_id):
        return User.query.get(user_id) if user_id else None

    def register_user(self, username, email, password):
        errors = []
        if not username or not email or not password:
            errors.append("Please fill in all fields.")
        if len(password) < 6:
            errors.append("Password must be at least 6 characters.")
        if User.query.filter_by(username=username).first():
            errors.append("This username is already taken.")
        if User.query.filter_by(email=email).first():
            errors.append("This email is already registered.")
        if errors:
            raise ValidationError(*errors)

        return self._create_user(username, email, password, role="user")

    def create_admin(self, username, email, password):
        if User.query.filter_by(username=username).first():
            raise ValidationError("This username already exists.")
        return self._create_user(username, email, password, role="admin")

    def _create_user(self, username, email, password, role):
        user = User(username=username, email=email, role=role)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user

    def authenticate(self, username, password):
        user = User.query.filter_by(username=username).first()
        if not user or not user.check_password(password):
            raise ValidationError("Incorrect username or password.")
        if not user.is_active_account:
            raise ValidationError("This account has been deactivated. Please contact an administrator.")

        user.last_login_at = datetime.utcnow()
        db.session.commit()
        return user

    # ---------------------------------------------------------- admin --
    def get_admin_dashboard_data(self):
        all_users = User.query.order_by(User.created_at.asc()).all()
        total_users = len(all_users)
        active_users = sum(1 for u in all_users if u.is_active_account)
        week_ago = datetime.utcnow() - timedelta(days=7)
        total_storage = sum(u.total_storage_bytes() for u in all_users)
        quota = self.config["ADMIN_TOTAL_QUOTA_BYTES"]
        percent_used = round((total_storage / quota) * 100, 1) if quota else 0

        return {
            "users": all_users,
            "total_users": total_users,
            "active_users": active_users,
            "inactive_users": total_users - active_users,
            "new_this_week": sum(1 for u in all_users if u.created_at and u.created_at >= week_ago),
            "total_documents": Document.query.filter_by(is_latest=True).count(),
            "total_storage": total_storage,
            "percent_used": min(percent_used, 100),
            "quota": quota,
        }

    def set_user_status(self, admin_id, user_id, status):
        user = User.query.get_or_404(user_id)
        if user.id == admin_id and status != "active":
            raise ValidationError("You cannot deactivate your own account.")
        user.is_active_account = (status == "active")
        db.session.commit()
        return user

    def delete_user(self, admin_id, user_id):
        user = User.query.get_or_404(user_id)
        if user.id == admin_id:
            raise ValidationError("You cannot delete your own account.")
        username = user.username
        self.storage.delete_user_folder(user.id)
        db.session.delete(user)
        db.session.commit()
        return username

    # ---------------------------------------------------------- user dashboard --
    def get_user_dashboard_data(self, user):
        all_latest = user.latest_documents()
        self._sync_categories(user, all_latest)

        categories = Category.query.filter_by(user_id=user.id).order_by(Category.name).all()
        total_storage = user.total_storage_bytes()
        quota = self.config["USER_QUOTA_BYTES"]
        percent_used = round((total_storage / quota) * 100, 1) if quota else 0

        return {
            "docs": all_latest,
            "all_docs": all_latest,
            "categories": categories,
            "total_documents": len(all_latest),
            "total_storage": total_storage,
            "percent_used": min(percent_used, 100),
            "quota": quota,
            "recent_count": sum(1 for d in all_latest if d.is_recent()),
        }

    def _sync_categories(self, user, documents):
        existing_names = {c.name for c in Category.query.filter_by(user_id=user.id).all()}
        doc_category_names = {d.category for d in documents if d.category and d.category != "Uncategorized"}
        missing_names = doc_category_names - existing_names
        if missing_names:
            for name in missing_names:
                db.session.add(Category(user_id=user.id, name=name))
            db.session.commit()

    # ---------------------------------------------------------- category --
    def add_category(self, user, name):
        name = (name or "").strip()
        self._validate_category_name(user, name)
        db.session.add(Category(user_id=user.id, name=name))
        db.session.commit()
        return name

    def rename_category(self, user, category_id, new_name):
        category = self._get_own_category(user, category_id)
        new_name = (new_name or "").strip()
        old_name = category.name

        check_duplicate = new_name.lower() != old_name.lower()
        self._validate_category_name(user, new_name, check_duplicate=check_duplicate)

        category.name = new_name
        Document.query.filter_by(user_id=user.id, category=old_name).update({"category": new_name})
        db.session.commit()
        return old_name, new_name

    def delete_category(self, user, category_id):
        category = self._get_own_category(user, category_id)
        old_name = category.name
        Document.query.filter_by(user_id=user.id, category=old_name).update({"category": "Uncategorized"})
        db.session.delete(category)
        db.session.commit()
        return old_name

    def _get_own_category(self, user, category_id):
        category = Category.query.get_or_404(category_id)
        if category.user_id != user.id:
            raise AccessDeniedError
        return category

    def _validate_category_name(self, user, name, check_duplicate=True):
        if not name:
            raise ValidationError("Category name can't be empty.")
        if name.lower() == "uncategorized":
            raise ValidationError("That name is reserved.")
        if check_duplicate and Category.query.filter(
            Category.user_id == user.id, db.func.lower(Category.name) == name.lower()
        ).first():
            raise ValidationError(f'You already have a category named "{name}".')

    # ---------------------------------------------------------- document --
    def upload_document(self, user, file, version_of="", title="", category="", notes=""):
        if version_of:
            return self.upload_new_version(user, version_of, file)

        self._validate_file(file)
        title = (title or "").strip() or file.filename.rsplit(".", 1)[0]
        category = (category or "").strip() or "Uncategorized"
        notes = (notes or "").strip()

        stored_filename, filesize = self.storage.save(user.id, file)

        doc = Document(
            user_id=user.id, group_id=new_uuid(), version=1, is_latest=True,
            title=title, category=category, notes=notes,
            original_filename=secure_filename(file.filename),
            stored_filename=stored_filename, filesize_bytes=filesize,
        )
        db.session.add(doc)
        db.session.commit()
        return doc

    def _validate_file(self, file):
        if not file or file.filename == "":
            raise ValidationError("Please choose a file to upload.")
        if not allowed_file(file.filename, self.config["ALLOWED_EXTENSIONS"]):
            raise ValidationError("Unsupported file format.")

    # ---------------------------------------------------------- version control --
    def upload_new_version(self, user, doc_id, file):
        doc = self.get_document_for(user, doc_id)
        if doc.user_id != user.id:
            raise AccessDeniedError
        self._validate_file(file)

        # keep the current version as a memento before it is replaced
        self.version_history.save(doc)

        stored_filename, filesize = self.storage.save(user.id, file)
        doc.version += 1
        doc.original_filename = secure_filename(file.filename)
        doc.stored_filename = stored_filename
        doc.filesize_bytes = filesize
        doc.uploaded_at = datetime.utcnow()
        db.session.commit()
        return doc

    def restore_version(self, user, doc_id, version):
        doc = self.get_document_for(user, doc_id)
        if doc.user_id != user.id:
            raise AccessDeniedError
        memento = self.version_history.get(doc, version)
        if memento is None:
            raise ValidationError("That version does not exist.")

        # keep the current version in the history, then restore the selected one
        self.version_history.save(doc)
        doc.restore_from_memento(memento)
        db.session.commit()
        return doc

    def get_version_history(self, doc):
        return self.version_history.get_history(doc)

    def get_all_versions(self, doc):
        # current version first, then the previous versions (newest first)
        return [doc.create_memento()] + self.get_version_history(doc)

    def get_document_for(self, user, doc_id):
        doc = Document.query.get_or_404(doc_id)
        if doc.user_id != user.id and not user.is_admin:
            raise AccessDeniedError
        return doc

    def update_document(self, user, doc_id, title=None, category=None, notes=None):
        doc = self.get_document_for(user, doc_id)
        doc.title = (title if title is not None else doc.title).strip() or doc.title
        doc.category = (category if category is not None else doc.category).strip() or "Uncategorized"
        doc.notes = (notes or "").strip()
        db.session.commit()
        return doc

    def get_download_info(self, user, doc_id):
        doc = self.get_document_for(user, doc_id)
        return self.storage.user_folder(doc.user_id), doc.stored_filename, doc.original_filename

    def delete_document(self, user, doc_id):
        doc = self.get_document_for(user, doc_id)
        owner_id = doc.user_id
        for d in Document.query.filter_by(group_id=doc.group_id).all():
            for memento in self.version_history.get_history(d):
                self.storage.delete(d.user_id, memento.stored_filename)
            self.storage.delete(d.user_id, d.stored_filename)
            db.session.delete(d)
        db.session.commit()
        return owner_id