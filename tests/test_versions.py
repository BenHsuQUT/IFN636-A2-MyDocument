import io
import os

from project.app import facade
from project.models import db
from flask import template_rendered


class TestUploadVersion:

    def test_should_upload_new_version_and_keep_previous(
        self, client, document
    ):
        original_filename = document.stored_filename
        new_content = b"Updated document content"

        response = client.post(
            f"/documents/{document.id}/versions/upload",
            data={
                "file": (io.BytesIO(new_content), "updated.txt"),
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith(
            f"/documents/{document.id}"
        )

        db.session.refresh(document)

        assert document.version == 2
        assert document.original_filename == "updated.txt"
        assert document.stored_filename != original_filename
        assert document.filesize_bytes == len(new_content)

        folder = facade.storage.user_folder(document.user_id)

        # New file contains the updated content
        with open(
            os.path.join(folder, document.stored_filename), "rb"
        ) as file:
            assert file.read() == new_content

        # Previous file and its version record are retained
        history = facade.get_version_history(document)
        assert len(history) == 1
        assert history[0].version == 1
        assert history[0].stored_filename == original_filename

        with open(
            os.path.join(folder, original_filename), "rb"
        ) as file:
            assert file.read() == b"hello world"

    def test_should_reject_unsupported_version_file(
        self, client, document
    ):
        original_filename = document.stored_filename

        response = client.post(
            f"/documents/{document.id}/versions/upload",
            data={
                "file": (io.BytesIO(b"invalid"), "virus.exe"),
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 302

        db.session.refresh(document)
        assert document.version == 1
        assert document.stored_filename == original_filename
        assert len(facade.get_version_history(document)) == 0

        with client.session_transaction() as session:
            assert any(
                category == "error"
                for category, message in session.get("_flashes", [])
            )

    def test_should_block_version_upload_to_another_users_document(
        self, client, other_document
    ):
        original_filename = other_document.stored_filename

        response = client.post(
            f"/documents/{other_document.id}/versions/upload",
            data={
                "file": (io.BytesIO(b"Unauthorised update"), "update.txt"),
            },
            content_type="multipart/form-data",
        )

        assert response.status_code == 403

        db.session.refresh(other_document)
        assert other_document.version == 1
        assert other_document.stored_filename == original_filename
        assert len(facade.get_version_history(other_document)) == 0


class TestVersionHistory:

    def test_should_display_current_and_previous_versions(
        self, app, client, document
    ):
        # Upload version 2 so the document has a history
        upload_response = client.post(
            f"/documents/{document.id}/versions/upload",
            data={
                "file": (
                    io.BytesIO(b"Version two content"),
                    "updated.txt",
                ),
            },
            content_type="multipart/form-data",
        )
        assert upload_response.status_code == 302

        contexts = []

        def capture_template(sender, template, context, **extra):
            contexts.append(context)

        with template_rendered.connected_to(capture_template, app):
            response = client.get(f"/documents/{document.id}")

        assert response.status_code == 200
        assert contexts

        versions = contexts[-1]["versions"]

        assert [version.version for version in versions] == [2, 1]
        assert versions[0].original_filename == "updated.txt"
        assert versions[1].original_filename == "report.txt"

        # Both versions have download links on the page
        assert (
            f"/documents/{document.id}/versions/1/download".encode()
            in response.data
        )
        assert (
            f"/documents/{document.id}/versions/2/download".encode()
            in response.data
        )


class TestDownloadVersion:

    def test_should_download_previous_version(self, client, document):
        response = client.post(
            f"/documents/{document.id}/versions/upload",
            data={
                "file": (
                    io.BytesIO(b"Version two content"),
                    "updated.txt",
                ),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 302

        response = client.get(
            f"/documents/{document.id}/versions/1/download"
        )

        assert response.status_code == 200
        assert response.data == b"hello world"

        disposition = response.headers["Content-Disposition"]
        assert "attachment" in disposition
        assert "report_V1.txt" in disposition

        response.close()

    def test_should_return_404_for_missing_version(
        self, client, document
    ):
        response = client.get(
            f"/documents/{document.id}/versions/9999/download"
        )

        assert response.status_code == 404


class TestRestoreVersion:

    def test_should_restore_previous_version(self, client, document):
        original_filename = document.stored_filename

        # Create version 2
        response = client.post(
            f"/documents/{document.id}/versions/upload",
            data={
                "file": (
                    io.BytesIO(b"Version two content"),
                    "updated.txt",
                ),
            },
            content_type="multipart/form-data",
        )
        assert response.status_code == 302

        db.session.refresh(document)
        assert document.version == 2
        version_two_filename = document.stored_filename

        # Restore version 1 as the newest version
        response = client.post(
            f"/documents/{document.id}/versions/1/restore"
        )

        assert response.status_code == 302
        assert response.headers["Location"].endswith(
            f"/documents/{document.id}"
        )

        db.session.refresh(document)
        assert document.version == 3
        assert document.original_filename == "report.txt"
        assert document.stored_filename == original_filename

        # Verify that the current download contains restored content
        response = client.get(
            f"/documents/{document.id}/download"
        )
        assert response.status_code == 200
        assert response.data == b"hello world"
        response.close()

        # Version 2 should remain available in history
        history = facade.get_version_history(document)
        version_two = next(
            (item for item in history if item.version == 2),
            None,
        )

        assert version_two is not None
        assert version_two.stored_filename == version_two_filename

        with open(
            os.path.join(
                facade.storage.user_folder(document.user_id),
                version_two_filename,
            ),
            "rb",
        ) as file:
            assert file.read() == b"Version two content"

    def test_should_reject_missing_version(self, client, document):
        original_filename = document.stored_filename

        response = client.post(
            f"/documents/{document.id}/versions/9999/restore"
        )

        assert response.status_code == 302
        db.session.refresh(document)

        assert document.version == 1
        assert document.stored_filename == original_filename
        assert len(facade.get_version_history(document)) == 0

        with client.session_transaction() as session:
            assert (
                "error", "That version does not exist."
            ) in session.get("_flashes", [])