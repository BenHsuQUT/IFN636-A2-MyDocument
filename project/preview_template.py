from abc import ABC, abstractmethod

from pathlib import Path

from docx import Document as WordDocument
from docx.table import Table
from docx.text.paragraph import Paragraph


class PreviewError(Exception):
    pass


class DocumentPreview(ABC):
    # Template for Document Preview that subclasses inherit
    def generate(self, file_path):
        path = Path(file_path)

        # Validate the stored file
        if not path.is_file():
            raise PreviewError("The document file could not be found.")
        # Prepare content according to the file type
        try:
            content = self.prepare_content(path)
        except (OSError, UnicodeError) as error:
            raise PreviewError("The document could not be read for preview.") from error
        # Return the result
        return {"type": self.preview_type, "content": content}

    @property
    @abstractmethod
    def preview_type(self):
        pass

    @abstractmethod
    def prepare_content(self, file_path):
        pass


class PdfPreview(DocumentPreview):
    @property
    def preview_type(self):
        return "pdf"

    # The browser displays the PDF through a protected route
    def prepare_content(self, file_path):
        return None


class TextPreview(DocumentPreview):
    @property
    def preview_type(self):
        return "text"

    def prepare_content(self, file_path):
        return file_path.read_text(encoding="utf-8-sig")


class DocxPreview(DocumentPreview):
    @property
    def preview_type(self):
        return "docx"

    def prepare_content(self, file_path):
        try:
            document = WordDocument(str(file_path))
            sections = []
            for item in document.iter_inner_content():
                if isinstance(item, Paragraph):
                    sections.append(item.text)
                elif isinstance(item, Table):
                    for row in item.rows:
                        sections.append(" | ".join(cell.text for cell in row.cells))
                    sections.append("")
            return "\n\n".join(sections)
        except Exception as error:
            raise PreviewError("The DOCX document could not be read for preview.") from error