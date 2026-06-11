from __future__ import annotations

from pathlib import Path
import re
import xml.etree.ElementTree as ET
from zipfile import ZipFile

from ..schemas import ParsedSection


def parse_pptx(file_path: str | Path) -> list[ParsedSection]:
    """Extract visible text from PPTX slides without requiring PowerPoint."""
    path = Path(file_path)
    sections: list[ParsedSection] = []

    with ZipFile(path) as archive:
        slide_names = sorted(
            (name for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name)),
            key=_slide_number,
        )
        for index, slide_name in enumerate(slide_names, start=1):
            raw_xml = archive.read(slide_name)
            text = _slide_text(raw_xml)
            if text:
                sections.append(
                    ParsedSection(
                        page_number=index,
                        raw_text=text,
                        section_title=_detect_section_title(text),
                    )
                )

    return sections


def _slide_text(raw_xml: bytes) -> str:
    try:
        root = ET.fromstring(raw_xml)
    except ET.ParseError:
        return ""

    parts: list[str] = []
    for node in root.iter():
        if node.tag.endswith("}t") and node.text:
            text = " ".join(node.text.split())
            if text:
                parts.append(text)
    return "\n".join(parts)


def _slide_number(name: str) -> int:
    match = re.search(r"slide(\d+)\.xml$", name)
    return int(match.group(1)) if match else 0


def _detect_section_title(text: str) -> str | None:
    for line in text.splitlines():
        candidate = " ".join(line.split())
        if len(candidate) >= 4:
            return candidate[:200]
    return None
