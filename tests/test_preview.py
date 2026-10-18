import os

from project.app import facade
from project.models import db
from docx import Document as WordDocument


class TestDocumentPreview:

    def test_should_preview_text_document(self, client, document):
        response = client.get(f"/documents/{document.id}")

        assert response.status_code == 200
        assert b"hello world" in response.data

    def test_should_serve_pdf_inline(self, client, document):
        # Prepare a PDF file in the temporary upload folder
        pdf_content = (
            b"%PDF-1.4\n"
            b"1 0 obj\n<< /Type /Catalog >>\nendobj\n"
            b"trailer\n<< /Root 1 0 R >>\n%%EOF"
        )

        document.original_filename = "report.pdf"
        document.stored_filename = "report_stored.pdf"
        document.filesize_bytes = len(pdf_content)
        db.session.commit()

        file_path = os.path.join(
            facade.storage.upload_folder,
            str(document.user_id),
            document.stored_filename,
        )

        with open(file_path, "wb") as file:
            file.write(pdf_content)

        response = client.get(
            f"/documents/{document.id}/preview/content"
        )

        assert response.status_code == 200
        assert response.mimetype == "application/pdf"
        assert response.data == pdf_content
        assert "inline" in response.headers["Content-Disposition"]
        assert response.headers["Cache-Control"] == "private, no-store"

        response.close()

    def test_should_reject_non_pdf_at_pdf_content_route(
        self, client, document
    ):
        response = client.get(
            f"/documents/{document.id}/preview/content"
        )

        assert response.status_code == 404

    def test_should_block_another_users_preview(
        self, client, other_document
    ):
        response = client.get(
            f"/documents/{other_document.id}/preview/content"
        )

        assert response.status_code == 403
        assert b"hello world" not in response.data

    def test_should_preview_docx_document(self, client, document):
        document.original_filename = "report.docx"
        document.stored_filename = "report_stored.docx"
        db.session.commit()

        file_path = os.path.join(
            facade.storage.upload_folder,
            str(document.user_id),
            document.stored_filename,
        )

        # Create a real DOCX file with identifiable text
        word_file = WordDocument()
        word_file.add_paragraph("Unique DOCX preview content")
        word_file.save(file_path)

        document.filesize_bytes = os.path.getsize(file_path)
        db.session.commit()

        response = client.get(f"/documents/{document.id}")

        assert response.status_code == 200
        assert b"Unique DOCX preview content" in response.data