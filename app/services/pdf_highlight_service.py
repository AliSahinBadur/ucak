from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from math import hypot
from pathlib import Path
import re
import shutil
import unicodedata

from ..config import APP_BRAND


@dataclass(frozen=True)
class PdfHighlightRequest:
    key: str
    page_start: int
    page_end: int
    excerpt: str
    color: str
    label: str


@dataclass
class PdfHighlightBuildResult:
    output_path: Path
    highlighted_passages: int
    page_by_key: dict[str, int]


@dataclass
class _TextFragment:
    text: str
    tokens: list[str]
    x: float
    y: float
    font_size: float
    width: float


class PdfHighlightService:
    """Create a review copy with paired source passages highlighted."""

    def build(
        self,
        source_path: str | Path,
        output_path: str | Path,
        requests: list[PdfHighlightRequest],
    ) -> PdfHighlightBuildResult:
        from pypdf import PdfReader, PdfWriter
        from pypdf.annotations import Highlight
        from pypdf.generic import (
            ArrayObject,
            FloatObject,
            NameObject,
            TextStringObject,
        )

        source = Path(source_path)
        target = Path(output_path)
        if source.suffix.lower() != ".pdf" or not source.exists():
            raise ValueError("PDF source file could not be found.")

        target.parent.mkdir(parents=True, exist_ok=True)
        reader = PdfReader(str(source))
        writer = PdfWriter()
        writer.clone_document_from_reader(reader)

        page_by_key: dict[str, int] = {}
        highlighted_passages = 0
        grouped_requests: dict[tuple[int, int, str, str], list[PdfHighlightRequest]] = {}
        for request in requests:
            excerpt_key = self._normalize_text(request.excerpt)
            if not excerpt_key:
                continue
            group_key = (
                max(int(request.page_start), 1),
                max(int(request.page_end), int(request.page_start), 1),
                excerpt_key,
                self._normalize_color(request.color),
            )
            grouped_requests.setdefault(group_key, []).append(request)

        for grouped in grouped_requests.values():
            request = grouped[0]
            match = self._find_best_match(reader, request)
            if match is None:
                continue
            page_index, rectangles = match
            if not rectangles:
                continue

            quad_points = ArrayObject()
            for left, bottom, right, top in rectangles:
                quad_points.extend(
                    [
                        FloatObject(left),
                        FloatObject(top),
                        FloatObject(right),
                        FloatObject(top),
                        FloatObject(left),
                        FloatObject(bottom),
                        FloatObject(right),
                        FloatObject(bottom),
                    ]
                )
            rect = (
                min(item[0] for item in rectangles),
                min(item[1] for item in rectangles),
                max(item[2] for item in rectangles),
                max(item[3] for item in rectangles),
            )
            annotation = Highlight(
                rect=rect,
                quad_points=quad_points,
                highlight_color=self._normalize_color(request.color),
                printing=True,
                title_bar=APP_BRAND.display_name,
            )
            annotation[NameObject("/Contents")] = TextStringObject(request.label[:240])
            annotation[NameObject("/CA")] = FloatObject(0.58)
            writer.add_annotation(page_number=page_index, annotation=annotation)

            highlighted_passages += 1
            for grouped_request in grouped:
                page_by_key[grouped_request.key] = page_index + 1

        temporary_path = target.with_suffix(".tmp.pdf")
        temporary_path.unlink(missing_ok=True)
        if highlighted_passages:
            with temporary_path.open("wb") as stream:
                writer.write(stream)
        else:
            shutil.copy2(source, temporary_path)
        temporary_path.replace(target)

        # Reopen the file so a corrupt annotation never reaches the browser.
        PdfReader(str(target))
        return PdfHighlightBuildResult(
            output_path=target,
            highlighted_passages=highlighted_passages,
            page_by_key=page_by_key,
        )

    def _find_best_match(
        self,
        reader,
        request: PdfHighlightRequest,
    ) -> tuple[int, list[tuple[float, float, float, float]]] | None:
        target_tokens = self._tokens(request.excerpt)
        if not target_tokens:
            return None

        first_page = max(request.page_start - 1, 0)
        last_page = min(max(request.page_end, request.page_start), len(reader.pages))
        best: tuple[float, int, list[_TextFragment], set[int]] | None = None
        for page_index in range(first_page, last_page):
            page = reader.pages[page_index]
            fragments = self._extract_fragments(page)
            score, selected = self._match_fragments(target_tokens, fragments)
            if not selected:
                continue
            if best is None or score > best[0]:
                best = (score, page_index, fragments, selected)

        if best is None or best[0] < 0.24:
            return None
        _, page_index, fragments, selected = best
        rectangles = self._rectangles_for_fragments(
            reader.pages[page_index],
            fragments,
            selected,
        )
        return page_index, rectangles

    @staticmethod
    def _extract_fragments(page) -> list[_TextFragment]:
        from pypdf._text_extraction import mult

        fragments: list[_TextFragment] = []

        def visitor(text, user_matrix, text_matrix, _font, font_size) -> None:
            cleaned = " ".join(str(text or "").split())
            tokens = PdfHighlightService._tokens(cleaned)
            if not cleaned or not tokens:
                return
            matrix = mult(text_matrix, user_matrix)
            x = float(matrix[4])
            y = float(matrix[5])
            size = max(float(font_size or 0.0), 4.0)
            scale_x = max(hypot(float(matrix[0]), float(matrix[1])), 0.2)
            width = PdfHighlightService._estimated_width(cleaned, size, scale_x)
            fragments.append(
                _TextFragment(
                    text=cleaned,
                    tokens=tokens,
                    x=x,
                    y=y,
                    font_size=size,
                    width=width,
                )
            )

        page.extract_text(visitor_text=visitor)
        return fragments

    @staticmethod
    def _match_fragments(
        target_tokens: list[str],
        fragments: list[_TextFragment],
    ) -> tuple[float, set[int]]:
        page_tokens: list[str] = []
        token_fragment_indexes: list[int] = []
        for fragment_index, fragment in enumerate(fragments):
            page_tokens.extend(fragment.tokens)
            token_fragment_indexes.extend([fragment_index] * len(fragment.tokens))
        if not page_tokens:
            return 0.0, set()

        matcher = SequenceMatcher(None, target_tokens, page_tokens, autojunk=False)
        raw_blocks = [block for block in matcher.get_matching_blocks() if block.size]
        minimum_block = 1 if len(target_tokens) <= 3 else 2
        blocks = [block for block in raw_blocks if block.size >= minimum_block]
        if not blocks:
            return 0.0, set()

        matched_tokens = sum(block.size for block in blocks)
        longest_block = max(block.size for block in blocks)
        coverage = matched_tokens / max(len(target_tokens), 1)
        continuity = longest_block / max(len(target_tokens), 1)
        score = coverage * 0.72 + continuity * 0.28
        if longest_block < min(3, len(target_tokens)) and coverage < 0.55:
            return score, set()

        selected: set[int] = set()
        significant_size = max(2, min(5, longest_block // 3))
        for block in blocks:
            if block.size < significant_size and coverage < 0.70:
                continue
            for token_index in range(block.b, block.b + block.size):
                selected.add(token_fragment_indexes[token_index])
        return score, selected

    @staticmethod
    def _rectangles_for_fragments(
        page,
        fragments: list[_TextFragment],
        selected: set[int],
    ) -> list[tuple[float, float, float, float]]:
        cropbox = page.cropbox
        page_left = float(cropbox.left)
        page_bottom = float(cropbox.bottom)
        page_right = float(cropbox.right)
        page_top = float(cropbox.top)
        page_width = max(page_right - page_left, 1.0)

        line_groups: list[list[int]] = []
        for index in sorted(selected, key=lambda item: (-fragments[item].y, fragments[item].x)):
            fragment = fragments[index]
            matching_line = next(
                (
                    line
                    for line in line_groups
                    if abs(fragments[line[0]].y - fragment.y)
                    <= max(fragment.font_size * 0.35, 2.0)
                ),
                None,
            )
            if matching_line is None:
                line_groups.append([index])
            else:
                matching_line.append(index)

        rectangles: list[tuple[float, float, float, float]] = []
        for line in line_groups[:24]:
            line.sort(key=lambda item: fragments[item].x)
            selected_fragments = [fragments[item] for item in line]
            left = min(fragment.x for fragment in selected_fragments)
            right = max(
                fragment.x + min(fragment.width, page_width * 0.72)
                for fragment in selected_fragments
            )
            largest_size = max(fragment.font_size for fragment in selected_fragments)
            baseline = sum(fragment.y for fragment in selected_fragments) / len(selected_fragments)
            bottom = baseline - largest_size * 0.25
            top = baseline + largest_size * 0.92
            left = max(page_left, min(left, page_right))
            right = max(left + 1.0, min(right, page_right))
            bottom = max(page_bottom, min(bottom, page_top))
            top = max(bottom + 1.0, min(top, page_top))
            if right - left >= 2.0 and top - bottom >= 2.0:
                rectangles.append((left, bottom, right, top))
        return rectangles

    @staticmethod
    def _estimated_width(text: str, font_size: float, scale_x: float) -> float:
        units = 0.0
        for character in text:
            if character.isspace():
                units += 0.30
            elif character in "ilI1.,:;!|'":
                units += 0.30
            elif character in "MW@%":
                units += 0.82
            else:
                units += 0.53
        return max(units * font_size * scale_x, font_size * 0.5)

    @staticmethod
    def _tokens(value: str) -> list[str]:
        normalized = PdfHighlightService._normalize_text(value)
        return re.findall(r"[a-z0-9]+", normalized)

    @staticmethod
    def _normalize_text(value: str) -> str:
        folded = unicodedata.normalize("NFKD", str(value or ""))
        ascii_value = "".join(character for character in folded if not unicodedata.combining(character))
        return re.sub(r"\s+", " ", ascii_value.casefold()).strip()

    @staticmethod
    def _normalize_color(value: str) -> str:
        cleaned = str(value or "").strip().lstrip("#")
        return cleaned.upper() if re.fullmatch(r"[0-9A-Fa-f]{6}", cleaned) else "F6C344"
