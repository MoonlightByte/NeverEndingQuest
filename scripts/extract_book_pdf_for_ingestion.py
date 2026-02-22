# SPDX-FileCopyrightText: 2024 MoonlightByte
# SPDX-License-Identifier: Fair-Source-1.0
# License: See LICENSE file in the repository root
# This software is subject to the terms of the Fair Source License.

"""
NeverEndingQuest Book PDF Extraction - Chunked ingestion preprocessor
Copyright (c) 2024 MoonlightByte
Licensed under Fair Source License 1.0

Converts a single PDF book into bounded text chunks for local-only
inspiration ingestion workflows. This prevents context-window overflows
by forcing one-book-at-a-time, chunked processing.

Outputs are intended for gitignored local folders (for example Docs/books/).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

def _utc_now_iso() -> str:
    """Return UTC timestamp in ISO8601 Z format."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _sha256_text(value: str) -> str:
    """Return SHA256 hash for input text."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    """Return SHA256 hash for file bytes."""
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _slugify_filename(name: str) -> str:
    """Create filesystem-safe slug from filename stem."""
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "_", name).strip("_")
    return cleaned.lower() if cleaned else "book"


def _normalize_text(text: str) -> str:
    """Normalize extracted PDF text for chunking."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def _estimate_tokens(text: str) -> int:
    """Estimate token count with tiktoken if available."""
    try:
        import tiktoken  # type: ignore

        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except Exception:
        words = len(re.findall(r"\S+", text))
        return int(words * 1.3)


@dataclass
class PageText:
    """Container for extracted page text."""

    page_number: int
    text: str


def _extract_pages(pdf_path: Path, max_pages: Optional[int]) -> List[PageText]:
    """Extract normalized text from PDF pages."""
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception as import_error:
        raise RuntimeError(
            "Missing dependency 'pypdf'. Install requirements or use the project virtualenv."
        ) from import_error

    reader = PdfReader(str(pdf_path))
    total_pages = len(reader.pages)
    limit = min(total_pages, max_pages) if max_pages is not None else total_pages

    pages: List[PageText] = []
    for index in range(limit):
        raw = reader.pages[index].extract_text() or ""
        pages.append(PageText(page_number=index + 1, text=_normalize_text(raw)))
    return pages


def _chunk_pages(pages: List[PageText], max_chars: int, overlap_chars: int) -> List[Dict[str, Any]]:
    """Create bounded overlapping chunks while preserving page boundaries."""
    chunks: List[Dict[str, Any]] = []
    chunk_index = 1

    current_text: str = ""
    current_start_page: Optional[int] = None
    current_end_page: Optional[int] = None

    for page in pages:
        page_text = page.text
        if not page_text:
            continue

        cursor = 0
        while cursor < len(page_text):
            remaining = max_chars - len(current_text)
            if remaining <= 0:
                chunk_text = current_text.strip()
                if chunk_text:
                    chunks.append(
                        {
                            "chunk_id": f"chunk_{chunk_index:04d}",
                            "start_page": current_start_page,
                            "end_page": current_end_page,
                            "char_count": len(chunk_text),
                            "token_estimate": _estimate_tokens(chunk_text),
                            "text": chunk_text,
                        }
                    )
                    chunk_index += 1

                overlap = chunk_text[-overlap_chars:] if overlap_chars > 0 else ""
                current_text = overlap
                current_start_page = current_end_page
                continue

            take = min(remaining, len(page_text) - cursor)
            slice_text = page_text[cursor : cursor + take]

            if not current_text:
                current_start_page = page.page_number
            current_end_page = page.page_number

            if current_text and not current_text.endswith("\n"):
                current_text += "\n"
            current_text += slice_text
            cursor += take

            if len(current_text) >= max_chars:
                chunk_text = current_text.strip()
                if chunk_text:
                    chunks.append(
                        {
                            "chunk_id": f"chunk_{chunk_index:04d}",
                            "start_page": current_start_page,
                            "end_page": current_end_page,
                            "char_count": len(chunk_text),
                            "token_estimate": _estimate_tokens(chunk_text),
                            "text": chunk_text,
                        }
                    )
                    chunk_index += 1

                overlap = chunk_text[-overlap_chars:] if overlap_chars > 0 else ""
                current_text = overlap
                current_start_page = current_end_page

    tail = current_text.strip()
    if tail:
        chunks.append(
            {
                "chunk_id": f"chunk_{chunk_index:04d}",
                "start_page": current_start_page,
                "end_page": current_end_page,
                "char_count": len(tail),
                "token_estimate": _estimate_tokens(tail),
                "text": tail,
            }
        )

    return chunks


def _default_output_dir(input_pdf: Path) -> Path:
    """Build default output directory next to source PDF."""
    return input_pdf.parent / "ingestion"


def _write_outputs(output_dir: Path, base_slug: str, manifest: Dict[str, Any], chunks: List[Dict[str, Any]]) -> Dict[str, str]:
    """Write manifest and chunk files."""
    output_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = output_dir / f"{base_slug}.manifest.json"
    chunks_jsonl_path = output_dir / f"{base_slug}.chunks.jsonl"

    with manifest_path.open("w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    with chunks_jsonl_path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            line = json.dumps(chunk, ensure_ascii=False)
            handle.write(line + "\n")

    return {
        "manifest": str(manifest_path),
        "chunks": str(chunks_jsonl_path),
    }


def build_manifest(input_pdf: Path, pages: List[PageText], chunks: List[Dict[str, Any]], max_chars: int, overlap_chars: int) -> Dict[str, Any]:
    """Build extraction manifest metadata."""
    text_concat = "\n\n".join(page.text for page in pages if page.text)
    return {
        "schema_version": "book-ingestion-manifest/v1",
        "generated_at": _utc_now_iso(),
        "input_pdf": str(input_pdf),
        "input_pdf_bytes": input_pdf.stat().st_size,
        "input_pdf_sha256": _sha256_file(input_pdf),
        "page_count_extracted": len(pages),
        "chunk_count": len(chunks),
        "chunking": {
            "max_chars": max_chars,
            "overlap_chars": overlap_chars,
        },
        "totals": {
            "char_count": len(text_concat),
            "token_estimate": _estimate_tokens(text_concat),
        },
        "copyright": {
            "local_only_recommended": True,
            "contains_source_text": True,
            "github_commit_recommended": False,
        },
    }


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(
        description="Extract one PDF book into bounded text chunks for local ingestion workflows."
    )
    parser.add_argument("--input", required=True, help="Path to a single PDF file")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Output directory for manifest/chunks (default: <input_dir>/ingestion)",
    )
    parser.add_argument("--max-chars", type=int, default=6000, help="Maximum characters per chunk")
    parser.add_argument("--overlap-chars", type=int, default=400, help="Overlap characters between chunks")
    parser.add_argument("--max-pages", type=int, default=None, help="Optional limit for page extraction")
    parser.add_argument("--preview", type=int, default=0, help="Print first N chunk previews")
    return parser.parse_args()


def main() -> int:
    """Run one-book PDF extraction."""
    args = parse_args()

    input_pdf = Path(args.input)
    if not input_pdf.exists():
        print(f"[ERROR] Input PDF not found: {input_pdf}")
        return 1
    if input_pdf.suffix.lower() != ".pdf":
        print(f"[ERROR] Input must be a PDF: {input_pdf}")
        return 1

    max_chars = int(args.max_chars)
    overlap_chars = int(args.overlap_chars)
    if max_chars <= 500:
        print("[ERROR] --max-chars must be greater than 500")
        return 1
    if overlap_chars < 0 or overlap_chars >= max_chars:
        print("[ERROR] --overlap-chars must be >= 0 and less than --max-chars")
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else _default_output_dir(input_pdf)
    base_slug = _slugify_filename(input_pdf.stem)

    print(f"[INFO] Extracting PDF: {input_pdf}")
    pages = _extract_pages(input_pdf, args.max_pages)
    print(f"[INFO] Pages extracted: {len(pages)}")

    chunks = _chunk_pages(pages, max_chars=max_chars, overlap_chars=overlap_chars)
    print(f"[INFO] Chunks created: {len(chunks)}")

    manifest = build_manifest(input_pdf, pages, chunks, max_chars=max_chars, overlap_chars=overlap_chars)
    output_paths = _write_outputs(output_dir, base_slug, manifest, chunks)

    print(f"[OK] Manifest: {output_paths['manifest']}")
    print(f"[OK] Chunks:   {output_paths['chunks']}")
    print("[NOTE] Output contains source text; keep in gitignored local-only storage.")

    preview_count = int(args.preview)
    if preview_count > 0:
        print("\n[PREVIEW]")
        for chunk in chunks[:preview_count]:
            text = chunk["text"].replace("\n", " ")
            snippet = text[:180] + ("..." if len(text) > 180 else "")
            print(
                f"- {chunk['chunk_id']} pages {chunk['start_page']}-{chunk['end_page']} "
                f"chars={chunk['char_count']} tokens~{chunk['token_estimate']} :: {snippet}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
