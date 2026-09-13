"""
Loads sample_policy.md and splits it into small, citable chunks.

We split on markdown '##' section headers first — this keeps each chunk
semantically coherent and gives us a real section title to cite, rather
than an arbitrary character-offset chunk. If a section is still longer
than chunk_size, we sub-split it with overlap.
"""
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Chunk:
    text: str
    section: str
    chunk_id: str


def _split_long_section(text: str, chunk_size: int, overlap: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    pieces = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        pieces.append(text[start:end])
        start = end - overlap
    return pieces


def load_and_chunk(path: Path, chunk_size: int = 500, overlap: int = 50) -> list[Chunk]:
    raw = path.read_text()

    # Split on '## Section...' headers, keeping the header with its body.
    sections = re.split(r"(?=^## )", raw, flags=re.MULTILINE)

    chunks: list[Chunk] = []
    idx = 0
    for section in sections:
        section = section.strip()
        if not section:
            continue

        header_match = re.match(r"^##\s+(.+)$", section, flags=re.MULTILINE)
        title = header_match.group(1).strip() if header_match else "OmniCare General Insurance Policy 2026"

        for piece in _split_long_section(section, chunk_size, overlap):
            piece = piece.strip()
            # Skip chunks that are just a bare header with no body content
            body_only = re.sub(r"^#+\s+.+$", "", piece, flags=re.MULTILINE).strip()
            if not body_only:
                continue
            chunks.append(Chunk(text=piece, section=title, chunk_id=f"chunk-{idx}"))
            idx += 1

    return chunks
