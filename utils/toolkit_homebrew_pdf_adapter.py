# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Utility - Toolkit Homebrew PDF Adapter
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Convert text-extractable PDF uploads into canonical Markdown for the
toolkit Homebrew ingest pipeline.

This software is free for non-commercial and educational use.
Commercial competing use is prohibited for 2 years from release.
See LICENSE file for full terms.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


PDF_EXTRACTOR_IDENTITY = "pypdf"
PDF_MINIMUM_TEXT_CHARS = 250


class PdfConversionError(RuntimeError):
    """Raised when a PDF upload cannot be converted to Markdown."""

    def __init__(self, message: str, report: Dict[str, Any]):
        super().__init__(message)
        self.report = report


def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO-8601 format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    """Return SHA-256 digest for file contents."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalize_pdf_text(text: str) -> str:
    """Normalize extracted PDF text for markdown output."""
    if not text:
        return ""

    normalized = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x0c", "\n")
    normalized = re.sub(r"[\x00-\x08\x0b\x0e-\x1f]", " ", normalized)
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _title_from_filename(source_filename: str) -> str:
    """Derive a readable title from the uploaded filename."""
    stem = Path(str(source_filename or "")).stem
    cleaned = re.sub(r"[_-]+", " ", stem).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.title() if cleaned else "Converted PDF"


def _build_report_base(
    *,
    pdf_path: Path,
    markdown_path: Path,
    source_filename: str,
    page_count: int,
    pages_with_text: int,
    extracted_chars: int,
    warnings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a deterministic conversion report shell."""
    size_bytes = pdf_path.stat().st_size if pdf_path.exists() else 0
    sha256 = _sha256_file(pdf_path) if pdf_path.exists() else ""
    return {
        "status": "error",
        "source_filename": source_filename,
        "source_pdf_path": str(pdf_path),
        "converted_markdown_path": str(markdown_path),
        "sha256": sha256,
        "size_bytes": size_bytes,
        "extractor": PDF_EXTRACTOR_IDENTITY,
        "page_count": page_count,
        "pages_with_text": pages_with_text,
        "extracted_chars": extracted_chars,
        "min_required_chars": PDF_MINIMUM_TEXT_CHARS,
        "warnings": warnings,
        "error_message": "",
        "generated_at": _utc_now_iso(),
    }


def _build_markdown_document(source_filename: str, title: str, pages: List[Dict[str, Any]]) -> str:
    """Render extracted PDF pages into simple Markdown."""
    lines = [
        f"# {title}",
        "",
        "> Converted from PDF upload for toolkit Homebrew ingest.",
        f"> Original file: {source_filename}",
        f"> Extractor: {PDF_EXTRACTOR_IDENTITY}",
        "",
    ]

    for page in pages:
        page_number = int(page.get("page_number") or 0)
        page_text = str(page.get("text") or "").strip()
        lines.append(f"## PDF Page {page_number}")
        lines.append("")
        if page_text:
            lines.extend(page_text.splitlines())
        else:
            lines.append("> No extractable text detected on this page.")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def convert_pdf_upload_to_markdown(
    pdf_path: Path,
    markdown_path: Path,
    source_filename: Optional[str] = None,
) -> Dict[str, Any]:
    """Convert one PDF upload into the canonical Markdown source file.

    Raises:
        PdfConversionError: if the PDF cannot be read or does not contain
            enough text for the Markdown-only ingest pipeline.
    """
    source_path = Path(pdf_path)
    output_path = Path(markdown_path)
    original_name = str(source_filename or source_path.name)

    if not source_path.exists() or not source_path.is_file():
        report = _build_report_base(
            pdf_path=source_path,
            markdown_path=output_path,
            source_filename=original_name,
            page_count=0,
            pages_with_text=0,
            extracted_chars=0,
            warnings=[],
        )
        report["error_message"] = "PDF upload failed: source file is missing or unreadable."
        raise PdfConversionError(report["error_message"], report)

    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as import_error:
        report = _build_report_base(
            pdf_path=source_path,
            markdown_path=output_path,
            source_filename=original_name,
            page_count=0,
            pages_with_text=0,
            extracted_chars=0,
            warnings=[],
        )
        report["error_message"] = (
            "PDF upload failed: missing pypdf dependency. Install the project virtualenv and retry."
        )
        raise PdfConversionError(report["error_message"], report) from import_error

    try:
        reader = PdfReader(str(source_path))
        if getattr(reader, "is_encrypted", False):
            report = _build_report_base(
                pdf_path=source_path,
                markdown_path=output_path,
                source_filename=original_name,
                page_count=0,
                pages_with_text=0,
                extracted_chars=0,
                warnings=[
                    {
                        "type": "encrypted_pdf",
                        "message": "PDF is encrypted and cannot be extracted in this MVP.",
                    }
                ],
            )
            report["error_message"] = (
                "PDF upload failed: encrypted PDFs are not supported in this MVP."
            )
            raise PdfConversionError(report["error_message"], report)

        page_total = len(reader.pages)
        pages: List[Dict[str, Any]] = []
        warnings: List[Dict[str, Any]] = []
        pages_with_text = 0
        extracted_chars = 0

        for index in range(page_total):
            raw_text = reader.pages[index].extract_text() or ""
            normalized_text = _normalize_pdf_text(raw_text)
            page_number = index + 1
            if normalized_text:
                pages_with_text += 1
                extracted_chars += len(normalized_text)
            else:
                warnings.append(
                    {
                        "type": "page_without_text",
                        "page": page_number,
                        "message": f"Page {page_number} has no extractable text.",
                    }
                )
            pages.append({"page_number": page_number, "text": normalized_text})

        report = _build_report_base(
            pdf_path=source_path,
            markdown_path=output_path,
            source_filename=original_name,
            page_count=page_total,
            pages_with_text=pages_with_text,
            extracted_chars=extracted_chars,
            warnings=warnings,
        )

        if pages_with_text <= 0:
            report["error_message"] = (
                "PDF upload failed: no extractable text was found. This MVP supports text-extractable PDFs only."
            )
            raise PdfConversionError(report["error_message"], report)

        if extracted_chars < PDF_MINIMUM_TEXT_CHARS:
            report["error_message"] = (
                "PDF upload failed: extracted text is below the minimum supported threshold. "
                "This MVP supports text-extractable PDFs only."
            )
            raise PdfConversionError(report["error_message"], report)

        markdown_text = _build_markdown_document(
            source_filename=original_name,
            title=_title_from_filename(original_name),
            pages=pages,
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown_text, encoding="utf-8")

        report.update(
            {
                "status": "success",
                "error_message": "",
                "converted_markdown_path": str(output_path),
                "generated_markdown_chars": len(markdown_text),
            }
        )
        return report

    except PdfConversionError:
        raise
    except Exception as exc:
        report = _build_report_base(
            pdf_path=source_path,
            markdown_path=output_path,
            source_filename=original_name,
            page_count=0,
            pages_with_text=0,
            extracted_chars=0,
            warnings=[],
        )
        report["error_message"] = f"PDF upload failed: {exc}"
        raise PdfConversionError(report["error_message"], report) from exc
