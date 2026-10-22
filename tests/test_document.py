import io
import os
from unittest.mock import patch

from project.app import facade
from project.models import db, Document


# ---------------------------------------------------------------- upload (create) --
class TestUploadDocument:

    def test_should_upload_new_document_successfully(self, client, user):
        # Stub the file storage so no real file is written (like sinon.stub)
        with patch.object(facade.storage, "save", return_value=("abc123.txt", 11)) as save_stub:
            response = client.post(
                "/upload",
                data={"file": (io.BytesIO(b"hello world"), "notes.txt"), "title": "My Notes", "category": "Work"},
                content_type="multipart/form-data",
            )

        assert save_stub.call_count == 1
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")

        doc = Document.query.filter_by(user_id=user.id).first()
        assert doc is not None
        assert doc.title == "My Notes"
        assert doc.category == "Work"
        assert doc.stored_filename == "abc123.txt"

    def test_should_reject_unsupported_file_type(self, client):
        response = client.post(
            "/upload",
            data={"file": (io.BytesIO(b"fake"), "virus.exe"), "title": "Bad file"},
            content_type="multipart/form-data",
        )

        assert response.status_code == 302
        assert Document.query.count() == 0

    def test_should_return_500_if_an_error_occurs(self, client):
        # Stub the database commit to throw an error
        with patch.object(db.session, "commit", side_effect=Exception("DB Error")):
            response = client.post(
                "/upload",
                data={"file": (io.BytesIO(b"hello"), "notes.txt")},
                content_type="multipart/form-data",
            )

        assert response.status_code == 500

    def test_should_save_uploaded_file_and_metadata(self, client, user):
        content = b"hello world"

        response = client.post(
            "/upload",
            data={
                "file": (io.BytesIO(content), "notes.txt"),
                "title": "My Notes",
                "category": "Work",
                "notes": "Test document",
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")

        doc = Document.query.filter_by(user_id=user.id).one()

        assert doc.title == "My Notes"
        assert doc.category == "Work"
        assert doc.notes == "Test document"
        assert doc.original_filename == "notes.txt"
        assert doc.stored_filename
        assert doc.filesize_bytes == len(content)
        assert doc.version == 1

        file_path = os.path.join(
            facade.storage.upload_folder,
            str(user.id),
            doc.stored_filename,
        )

        assert os.path.isfile(file_path)

        with open(file_path, "rb") as saved_file:
            assert saved_file.read() == content

    def test_should_reject_upload_without_file(self, client):
        count_before = Document.query.count()

        response = client.post(
            "/upload",
            data={"title": "Missing file"},
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith("/dashboard")
        assert Document.query.count() == count_before

        with client.session_transaction() as session:
            assert any(
                category == "error"
                for category, message in session.get("_flashes", [])
            )


# ---------------------------------------------------------------- view (read) --
class TestViewDocument:

    def test_should_show_own_document(self, client, document):
        response = client.get(f"/documents/{document.id}")

        assert response.status_code == 200
        assert b"Report" in response.data

    def test_should_return_403_for_another_users_document(self, client, other_document):
        response = client.get(f"/documents/{other_document.id}")

        assert response.status_code == 403

    def test_should_return_404_if_document_is_not_found(self, client):
        response = client.get("/documents/9999")

        assert response.status_code == 404

    def test_should_redirect_to_login_if_not_logged_in(self, app, document):
        guest = app.test_client()
        response = guest.get(f"/documents/{document.id}")

        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------- update --
class TestUpdateDocument:

    def test_should_update_document_successfully(self, client, document):
        response = client.post(
            f"/documents/{document.id}/update",
            data={"title": "Updated Report", "category": "Finance", "notes": "checked"},
        )

        assert response.status_code == 302
        updated = db.session.get(Document, document.id)
        assert updated.title == "Updated Report"
        assert updated.category == "Finance"
        assert updated.notes == "checked"

    def test_should_return_403_for_another_users_document(self, client, other_document):
        response = client.post(f"/documents/{other_document.id}/update", data={"title": "Hacked"})

        assert response.status_code == 403
        assert db.session.get(Document, other_document.id).title == "Secret"

    def test_should_return_404_if_document_is_not_found(self, client):
        response = client.post("/documents/9999/update", data={"title": "Nothing"})

        assert response.status_code == 404

    def test_should_return_500_on_error(self, client, document):
        with patch.object(db.session, "commit", side_effect=Exception("DB Error")):
            response = client.post(f"/documents/{document.id}/update", data={"title": "New"})

        assert response.status_code == 500


# ---------------------------------------------------------------- delete --
class TestDeleteDocument:

    def test_should_delete_document_successfully(self, client, user, document):
        file_path = os.path.join(facade.storage.upload_folder, str(user.id), document.stored_filename)
        doc_id = document.id
        assert os.path.exists(file_path)

        response = client.post(f"/documents/{doc_id}/delete")

        assert response.status_code == 302
        assert db.session.get(Document, doc_id) is None
        assert not os.path.exists(file_path)

    def test_should_return_404_if_document_is_not_found(self, client):
        response = client.post("/documents/9999/delete")

        assert response.status_code == 404

    def test_should_return_500_if_an_error_occurs(self, client, document):
        with patch.object(db.session, "commit", side_effect=Exception("DB Error")):
            response = client.post(f"/documents/{document.id}/delete")

        assert response.status_code == 500

    def test_should_reject_deleting_another_users_document(
        self, client, other_document
    ):
        doc_id = other_document.id
        file_path = os.path.join(
            facade.storage.upload_folder,
            str(other_document.user_id),
            other_document.stored_filename,
        )

        assert os.path.isfile(file_path)

        response = client.post(f"/documents/{doc_id}/delete")

        assert response.status_code == 403
        assert db.session.get(Document, doc_id) is not None
        assert os.path.isfile(file_path)

# ---------------------------------------------------------------- download --

class TestDownloadDocument:

    def test_should_download_own_document(self, client, document):
        response = client.get(
            f"/documents/{document.id}/download"
        )

        assert response.status_code == 200
        assert response.data == b"hello world"

        disposition = response.headers["Content-Disposition"]
        assert "attachment" in disposition
        assert document.original_filename in disposition

        response.close()

    def test_should_reject_another_users_document(
        self, client, other_document
    ):
        response = client.get(
            f"/documents/{other_document.id}/download"
        )

        assert response.status_code == 403
        assert b"hello world" not in response.data

    def test_should_return_404_for_missing_document(self, client):
        response = client.get("/documents/9999/download")

        assert response.status_code == 404
