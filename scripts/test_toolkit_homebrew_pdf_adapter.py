"""Regression tests for the toolkit Homebrew PDF adapter."""

import tempfile
import os
import sys
import unittest
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DictionaryObject, NameObject, StreamObject

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.toolkit_homebrew_pdf_adapter import (
    PdfConversionError,
    PDF_MINIMUM_TEXT_CHARS,
    convert_pdf_upload_to_markdown,
)


class TestToolkitHomebrewPdfAdapter(unittest.TestCase):
    """Verify direct PDF conversion behavior."""

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _escape_pdf_text(self, text: str) -> str:
        return (
            str(text or "")
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )

    def _write_text_pdf(self, path: Path, page_texts: list[str], encrypted: bool = False) -> Path:
        writer = PdfWriter()
        for page_text in page_texts:
            page = writer.add_blank_page(width=612, height=792)
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            font_ref = writer._add_object(font)
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {NameObject("/F1"): font_ref}
                    )
                }
            )
            content = StreamObject()
            content._data = (
                f"BT /F1 12 Tf 72 720 Td ({self._escape_pdf_text(page_text)}) Tj ET".encode(
                    "latin-1"
                )
            )
            page[NameObject("/Contents")] = writer._add_object(content)

        if encrypted:
            writer.encrypt("secret")

        with path.open("wb") as handle:
            writer.write(handle)

        return path

    def test_convert_pdf_to_markdown_success(self) -> None:
        pdf_path = Path(self.temp_dir.name) / "converted_adventure.pdf"
        markdown_path = Path(self.temp_dir.name) / "converted_adventure.md"
        self._write_text_pdf(
            pdf_path,
            [
                "This first page contains enough extracted text to clear the minimum threshold. "
                "The helper should preserve page order and emit a readable Markdown file.",
                "This second page adds more text so the conversion report can record multiple pages "
                "with extractable text and a deterministic char count.",
            ],
        )

        report = convert_pdf_upload_to_markdown(pdf_path, markdown_path, "converted_adventure.pdf")

        self.assertEqual(report.get("status"), "success")
        self.assertEqual(report.get("extractor"), "pypdf")
        self.assertEqual(report.get("source_filename"), "converted_adventure.pdf")
        self.assertEqual(report.get("page_count"), 2)
        self.assertEqual(report.get("pages_with_text"), 2)
        self.assertGreater(int(report.get("extracted_chars") or 0), PDF_MINIMUM_TEXT_CHARS)
        self.assertTrue(markdown_path.exists())

        markdown = markdown_path.read_text(encoding="utf-8")
        self.assertIn("# Converted Adventure", markdown)
        self.assertIn("Converted from PDF upload for toolkit Homebrew ingest.", markdown)
        self.assertIn("## PDF Page 1", markdown)
        self.assertIn("## PDF Page 2", markdown)

    def test_convert_pdf_without_text_fails_closed(self) -> None:
        pdf_path = Path(self.temp_dir.name) / "blank.pdf"
        markdown_path = Path(self.temp_dir.name) / "blank.md"
        self._write_text_pdf(pdf_path, ["", ""], encrypted=False)

        with self.assertRaises(PdfConversionError) as caught:
            convert_pdf_upload_to_markdown(pdf_path, markdown_path, "blank.pdf")

        self.assertFalse(markdown_path.exists())
        report = caught.exception.report
        self.assertEqual(report.get("status"), "error")
        self.assertEqual(report.get("pages_with_text"), 0)
        self.assertIn("no extractable text", str(report.get("error_message") or "").lower())

    def test_convert_pdf_too_little_text_fails_closed(self) -> None:
        pdf_path = Path(self.temp_dir.name) / "short.pdf"
        markdown_path = Path(self.temp_dir.name) / "short.md"
        self._write_text_pdf(pdf_path, ["Too short for the supported threshold."])

        with self.assertRaises(PdfConversionError) as caught:
            convert_pdf_upload_to_markdown(pdf_path, markdown_path, "short.pdf")

        report = caught.exception.report
        self.assertEqual(report.get("status"), "error")
        self.assertLess(int(report.get("extracted_chars") or 0), PDF_MINIMUM_TEXT_CHARS)
        self.assertIn("minimum supported threshold", str(caught.exception).lower())

    def test_convert_encrypted_pdf_fails_closed(self) -> None:
        pdf_path = Path(self.temp_dir.name) / "encrypted.pdf"
        markdown_path = Path(self.temp_dir.name) / "encrypted.md"
        self._write_text_pdf(pdf_path, ["Encrypted pages should never reach the pipeline."], encrypted=True)

        with self.assertRaises(PdfConversionError) as caught:
            convert_pdf_upload_to_markdown(pdf_path, markdown_path, "encrypted.pdf")

        report = caught.exception.report
        self.assertEqual(report.get("status"), "error")
        self.assertIn("encrypted pdfs", str(caught.exception).lower())


if __name__ == "__main__":
    unittest.main()
