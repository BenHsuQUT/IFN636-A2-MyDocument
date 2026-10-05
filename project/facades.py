import os
import uuid

from werkzeug.utils import secure_filename

from project.models import db, Document, Category, new_uuid
from project.utils import allowed_file


class ValidationError(Exception):
    def __init__(self, *messages):
        super().__init__(*messages)
        self.messages = list(messages)


class AccessDeniedError(Exception):
    pass


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


class DocumentManagerFacade:
    def __init__(self, config):
        self.config = config
        self.storage = FileStorage(config["UPLOAD_FOLDER"])

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

    def upload_document(self, user, file, version_of="", title="", category="", notes=""):
        if not file or file.filename == "":
            raise ValidationError("Please choose a file to upload.")
        if not allowed_file(file.filename, self.config["ALLOWED_EXTENSIONS"]):
            raise ValidationError("Unsupported file format.")

        title = (title or "").strip()
        category = (category or "").strip() or "Uncategorized"
        notes = (notes or "").strip()

        stored_filename, filesize = self.storage.save(user.id, file)

        parent = None
        if version_of:
            parent = Document.query.filter_by(id=version_of, user_id=user.id, is_latest=True).first()

        if parent:
            parent.is_latest = False
            new_version = parent.version + 1
            group_id = parent.group_id
            title = parent.title
            category = parent.category
        else:
            group_id = new_uuid()
            new_version = 1
            if not title:
                title = file.filename.rsplit(".", 1)[0]

        doc = Document(
            user_id=user.id, group_id=group_id, version=new_version, is_latest=True,
            title=title, category=category, notes=notes,
            original_filename=secure_filename(file.filename),
            stored_filename=stored_filename, filesize_bytes=filesize,
        )
        db.session.add(doc)
        db.session.commit()
        return doc

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
            self.storage.delete(d.user_id, d.stored_filename)
            db.session.delete(d)
        db.session.commit()
        return owner_id
