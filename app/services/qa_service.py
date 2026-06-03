from __future__ import annotations

import re

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db.models import DocumentChunk
from .search_service import SearchService


class QAService:
    MIN_ANSWER_SCORE = 0.58
    MIN_TOKEN_OVERLAP_RATIO = 0.18
    MIN_SECTION_TITLE_OVERLAP = 0.22
    QA_CANDIDATE_MULTIPLIER = 3
    SUPPLEMENTAL_CANDIDATE_LIMIT = 12
    TOKEN_SYNONYMS = {
        "data": {"data", "veri", "verisi", "datasi", "datasi"},
        "veri": {"data", "veri", "verisi", "datasi", "datasi"},
        "verisi": {"data", "veri", "verisi", "datasi", "datasi"},
        "datasi": {"data", "veri", "verisi", "datasi", "datasi"},
        "datasi": {"data", "veri", "verisi", "datasi", "datasi"},
        "parkur": {"parkur", "parkuru", "parkurlari", "parkurlari", "guzergah", "rota"},
        "parkurlari": {"parkur", "parkuru", "parkurlari", "guzergah", "rota"},
        "guzergah": {"parkur", "parkuru", "parkurlari", "guzergah", "rota"},
        "guzergahlar": {"parkur", "parkuru", "parkurlari", "guzergah", "guzergahlar", "rota", "yol", "yollar"},
        "yol": {"yol", "yollar", "yollardan", "parkur", "parkurlari", "guzergah", "rota"},
        "yollar": {"yol", "yollar", "yollardan", "parkur", "parkurlari", "guzergah", "rota"},
        "yollardan": {"yol", "yollar", "yollardan", "parkur", "parkurlari", "guzergah", "rota"},
        "toplama": {"toplama", "toplanan", "toplanmasi"},
        "toplanan": {"toplama", "toplanan", "toplanmasi"},
        "toplanmasi": {"toplama", "toplanan", "toplanmasi", "toplanmakta"},
        "toplanmakta": {"toplama", "toplanan", "toplanmasi", "toplanmakta"},
        "ekipman": {"ekipman", "ekipmanlari", "enstrumantasyon"},
        "ekipmanlari": {"ekipman", "ekipmanlari", "enstrumantasyon"},
    }

    def __init__(self, session: Session) -> None:
        self.session = session
        self.search_service = SearchService(session)

    def answer_question(
        self,
        question: str,
        mode: str = "hybrid",
        limit: int = 5,
        document_id: int | None = None,
        document_ids: list[int] | None = None,
    ) -> dict:
        cleaned_question = " ".join(question.split())
        scoped_document_ids = self._resolve_document_scope(document_id=document_id, document_ids=document_ids)
        results = self._run_search(
            cleaned_question,
            mode=mode,
            limit=limit,
            document_id=document_id,
            document_ids=scoped_document_ids,
        )
        if not results:
            return {
                "question": cleaned_question,
                "mode": mode,
                "answer": "Bu soruya dayanarak yeterince guclu bir kaynak pasaj bulunamadi.",
                "answer_found": False,
                "confidence": 0.0,
                "embedding_provider": self.search_service.embedding_provider_name(),
                "sources": [],
            }

        answer, answer_score = self._build_answer(cleaned_question, results)
        answer_found = answer_score >= self.MIN_ANSWER_SCORE
        return {
            "question": cleaned_question,
            "mode": mode,
            "answer": answer if answer_found else "Bu soruya yakin gorunen pasajlar bulundu ama guvenilir bir kisa cevap secilemedi.",
            "answer_found": answer_found,
            "confidence": round(self._normalize_confidence(answer_score), 3),
            "embedding_provider": self.search_service.embedding_provider_name(),
            "sources": results[:3],
        }

    def _run_search(
        self,
        question: str,
        mode: str,
        limit: int,
        document_id: int | None = None,
        document_ids: list[int] | None = None,
    ) -> list[dict]:
        candidate_limit = max(limit * self.QA_CANDIDATE_MULTIPLIER, limit)
        question_profile = self._question_profile(question)
        scoped_document_ids = self._resolve_document_scope(document_id=document_id, document_ids=document_ids)
        base_results: list[dict] = []
        for query_variant in self._question_variants(question, question_profile):
            if mode == "keyword":
                variant_results = self.search_service.keyword_search(
                    query_variant,
                    limit=candidate_limit,
                    document_ids=scoped_document_ids,
                )
            elif mode == "semantic":
                variant_results = self.search_service.semantic_search(
                    query_variant,
                    limit=candidate_limit,
                    document_ids=scoped_document_ids,
                )
            else:
                variant_results = self.search_service.hybrid_search(
                    query_variant,
                    limit=candidate_limit,
                    document_ids=scoped_document_ids,
                )
            base_results = self._merge_result_lists(base_results, variant_results)
        supplemental_results = self._supplemental_chunk_candidates(
            question_profile,
            document_id=document_id,
            document_ids=scoped_document_ids,
        )
        merged_results = self._merge_result_lists(base_results, supplemental_results)
        if not scoped_document_ids:
            return merged_results
        if merged_results:
            return merged_results
        if len(scoped_document_ids) == 1:
            return self._document_chunk_candidates(question_profile, document_id=scoped_document_ids[0])
        return self._documents_chunk_candidates(question_profile, document_ids=scoped_document_ids)

    def _build_answer(self, question: str, results: list[dict]) -> tuple[str, float]:
        question_tokens = self.search_service.embedding_service.tokenize(question)
        question_profile = self._question_profile(question)
        ranked_results = self._prioritize_results_for_question(question_tokens, question_profile, results)
        contexts = self._build_candidate_contexts(question_tokens, ranked_results, question_profile)

        if question_profile["wants_list"]:
            list_answer, list_score = self._build_list_answer(contexts)
            if list_answer:
                return list_answer, list_score

        best_sentence = ""
        best_score = -1.0
        for context in contexts:
            for sentence in self._split_sentences(context["text"]):
                score = self._sentence_score(
                    question_tokens=question_tokens,
                    question=question,
                    sentence=sentence,
                    context=context,
                    question_profile=question_profile,
                )
                if score > best_score:
                    best_score = score
                    best_sentence = sentence

        if best_sentence:
            return best_sentence, best_score

        top_chunk = ranked_results[0]["chunk_text"]
        compact = " ".join(top_chunk.split())
        if len(compact) <= 280:
            return compact, 0.0
        return compact[:277].rstrip() + "...", 0.0

    def _prioritize_results_for_question(
        self,
        question_tokens: list[str],
        question_profile: dict,
        results: list[dict],
    ) -> list[dict]:
        ranked: list[tuple[float, dict]] = []
        subject_tokens = question_profile["subject_tokens"]
        subject_text = question_profile["subject_text"]
        subject_aliases = question_profile["subject_aliases"]

        for rank, result in enumerate(results):
            section_title = result.get("section_title") or ""
            normalized_chunk = self._normalize_text(result["chunk_text"])
            normalized_section = self._normalize_text(section_title)
            section_overlap = self._section_overlap(question_tokens, section_title)
            subject_overlap = self._text_overlap(subject_tokens, result["chunk_text"])
            title_subject_overlap = self._text_overlap(subject_tokens, section_title)
            exact_subject_bonus = 0.45 if self._contains_any_alias(normalized_chunk, subject_aliases) else 0.0
            exact_section_bonus = 0.55 if self._contains_any_alias(normalized_section, subject_aliases) else 0.0
            list_pattern_bonus = 0.22 if question_profile["wants_list"] and self._looks_like_list_block(result["chunk_text"]) else 0.0
            section_list_bonus = 0.18 if question_profile["wants_list"] and self._looks_like_list_title(section_title) else 0.0
            retrieval_score = max(
                float(result.get("combined_score", 0.0) or 0.0),
                float(result.get("semantic_score", 0.0) or 0.0),
                float(result.get("keyword_score", 0.0) or 0.0),
            )
            rank_bonus = max(0.12 - rank * 0.015, 0.0)
            score = (
                retrieval_score
                + section_overlap * 0.45
                + subject_overlap * 0.7
                + title_subject_overlap * 0.8
                + exact_subject_bonus
                + exact_section_bonus
                + list_pattern_bonus
                + section_list_bonus
                + rank_bonus
            )
            ranked.append((score, result))

        ranked.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in ranked]

    def _build_candidate_contexts(
        self,
        question_tokens: list[str],
        results: list[dict],
        question_profile: dict,
    ) -> list[dict]:
        contexts: list[dict] = []
        seen_keys: set[tuple] = set()

        for rank, result in enumerate(results):
            base_context = {
                "text": result["chunk_text"],
                "rank": rank,
                "result": result,
                "scope": "chunk",
                "section_match": self._section_overlap(question_tokens, result.get("section_title")),
                "question_profile": question_profile,
            }
            self._append_context(contexts, seen_keys, base_context)

            section_context = self._build_section_context(question_tokens, result, rank, question_profile)
            if section_context:
                self._append_context(contexts, seen_keys, section_context)

        return contexts

    def _build_section_context(
        self,
        question_tokens: list[str],
        result: dict,
        rank: int,
        question_profile: dict,
    ) -> dict | None:
        section_title = (result.get("section_title") or "").strip()
        document_id = int(result.get("document_id", 0) or 0)
        if document_id <= 0 or not section_title:
            return None

        section_overlap = self._section_overlap(question_tokens, section_title)
        if question_profile["wants_list"]:
            if section_overlap < self.MIN_SECTION_TITLE_OVERLAP or not self._looks_like_list_title(section_title):
                return None
        elif section_overlap < self.MIN_SECTION_TITLE_OVERLAP:
            return None

        section_rows = self.session.execute(
            select(DocumentChunk.chunk_text, DocumentChunk.chunk_order)
            .where(
                DocumentChunk.document_id == document_id,
                DocumentChunk.section_title == section_title,
            )
            .order_by(DocumentChunk.chunk_order.asc())
        ).all()
        if not section_rows:
            return None

        merged_text = "\n".join(row.chunk_text for row in section_rows if row.chunk_text.strip())
        if not merged_text.strip():
            return None

        return {
            "text": merged_text,
            "rank": rank,
            "result": result,
            "scope": "section",
            "section_match": section_overlap + 0.12,
            "question_profile": question_profile,
        }

    @staticmethod
    def _append_context(contexts: list[dict], seen_keys: set[tuple], context: dict) -> None:
        key = (
            int(context["result"].get("id", 0) or 0),
            context["scope"],
            len(context["text"]),
        )
        if key in seen_keys:
            return
        seen_keys.add(key)
        contexts.append(context)

    def _build_list_answer(self, contexts: list[dict]) -> tuple[str, float]:
        best_items: list[str] = []
        best_score = -1.0

        for context in contexts:
            items, header_text = self._extract_list_items(
                context["text"],
                context["question_profile"]["subject_text"],
            )
            if not items:
                continue

            score = self._list_score(items=items, header_text=header_text, context=context)
            if score > best_score:
                best_score = score
                best_items = items

        if not best_items:
            return "", -1.0

        answer = "\n".join(f"{index + 1}. {item}" for index, item in enumerate(best_items[:8]))
        return answer, best_score

    def _supplemental_chunk_candidates(
        self,
        question_profile: dict,
        document_id: int | None = None,
        document_ids: list[int] | None = None,
    ) -> list[dict]:
        subject_search_terms = question_profile["subject_search_terms"]
        if not subject_search_terms:
            return []

        token_conditions = [DocumentChunk.chunk_text.ilike(f"%{token}%") for token in subject_search_terms]
        token_conditions.extend(DocumentChunk.section_title.ilike(f"%{token}%") for token in subject_search_terms)
        statement = self.search_service._base_chunk_query().where(or_(*token_conditions))
        scoped_document_ids = self._resolve_document_scope(document_id=document_id, document_ids=document_ids)
        if len(scoped_document_ids) == 1:
            statement = statement.where(DocumentChunk.document_id == scoped_document_ids[0])
        elif scoped_document_ids:
            statement = statement.where(DocumentChunk.document_id.in_(scoped_document_ids))
        rows = self.session.execute(statement.limit(self.SUPPLEMENTAL_CANDIDATE_LIMIT * 4)).all()

        return self._score_candidate_rows(rows, question_profile)

    def _document_chunk_candidates(self, question_profile: dict, document_id: int) -> list[dict]:
        rows = self.session.execute(
            self.search_service._base_chunk_query()
            .where(DocumentChunk.document_id == document_id)
            .limit(self.SUPPLEMENTAL_CANDIDATE_LIMIT * 8)
        ).all()
        return self._score_candidate_rows(rows, question_profile)

    def _documents_chunk_candidates(self, question_profile: dict, document_ids: list[int]) -> list[dict]:
        rows = self.session.execute(
            self.search_service._base_chunk_query()
            .where(DocumentChunk.document_id.in_(document_ids))
            .limit(self.SUPPLEMENTAL_CANDIDATE_LIMIT * 12)
        ).all()
        return self._score_candidate_rows(rows, question_profile)

    def _score_candidate_rows(self, rows: list, question_profile: dict) -> list[dict]:
        scored: list[tuple[float, dict]] = []
        subject_aliases = question_profile["subject_aliases"]
        for row in rows:
            section_title = row.section_title or ""
            normalized_chunk = self._normalize_text(row.chunk_text)
            normalized_section = self._normalize_text(section_title)
            subject_overlap = self._text_overlap(question_profile["subject_tokens"], row.chunk_text)
            section_overlap = self._text_overlap(question_profile["subject_tokens"], section_title)
            exact_phrase_bonus = 0.95 if self._contains_any_alias(normalized_chunk, subject_aliases) else 0.0
            exact_section_bonus = 1.05 if self._contains_any_alias(normalized_section, subject_aliases) else 0.0
            list_bonus = 0.28 if question_profile["wants_list"] and self._looks_like_list_block(row.chunk_text) else 0.0
            score = (
                subject_overlap * 1.4
                + section_overlap * 1.7
                + exact_phrase_bonus
                + exact_section_bonus
                + list_bonus
            )
            if score <= 0.0:
                continue
            scored.append(
                (
                    score,
                    {
                        "id": row.id,
                        "document_id": row.document_id,
                        "document_title": row.document_title,
                        "file_name": row.file_name,
                        "page_start": row.page_start,
                        "page_end": row.page_end,
                        "section_title": row.section_title,
                        "chunk_text": row.chunk_text,
                        "match_type": "keyword",
                        "keyword_score": score,
                        "semantic_score": 0.0,
                        "combined_score": score,
                    },
                )
            )

        scored.sort(key=lambda item: item[0], reverse=True)
        return [item for _, item in scored[: self.SUPPLEMENTAL_CANDIDATE_LIMIT]]

    @staticmethod
    def _merge_result_lists(primary: list[dict], secondary: list[dict]) -> list[dict]:
        merged: dict[int, dict] = {}
        for item in primary:
            merged[int(item["id"])] = dict(item)
        for item in secondary:
            item_id = int(item["id"])
            if item_id in merged:
                merged[item_id]["keyword_score"] = max(
                    float(merged[item_id].get("keyword_score", 0.0) or 0.0),
                    float(item.get("keyword_score", 0.0) or 0.0),
                )
                merged[item_id]["combined_score"] = max(
                    float(merged[item_id].get("combined_score", 0.0) or 0.0),
                    float(item.get("combined_score", 0.0) or 0.0),
                )
            else:
                merged[item_id] = dict(item)
        return list(merged.values())

    @staticmethod
    def _resolve_document_scope(document_id: int | None = None, document_ids: list[int] | None = None) -> list[int]:
        combined: list[int] = []
        if document_ids:
            combined.extend(document_ids)
        if document_id is not None:
            combined.append(document_id)
        return SearchService._normalize_document_ids(combined)

    @staticmethod
    def _looks_like_list_block(text: str) -> bool:
        normalized = " ".join(text.split())
        numbered_count = len(re.findall(r"(?:^|\s)\d+[.)]\s+", normalized))
        bullet_count = len(re.findall(r"\s+[•-]\s+", normalized))
        return numbered_count >= 2 or bullet_count >= 2

    @staticmethod
    def _looks_like_list_title(section_title: str) -> bool:
        lowered = QAService._normalize_text(section_title or "")
        return any(
            token in lowered
            for token in ("parkur", "liste", "madde", "adim", "senaryo", "kosul", "ekipman", "deger", "olcum")
        )

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        compact = " ".join(text.split())
        if not compact:
            return []
        parts = re.split(r"(?<=[.!?;:])\s+|\s+[•-]\s+", compact)
        sentences = [part.strip() for part in parts if part.strip()]
        return sentences or [compact]

    @staticmethod
    def _extract_list_items(text: str, subject_text: str = "") -> tuple[list[str], str]:
        normalized = text.replace("\r", "\n")
        lowered = normalized.lower()
        normalized_subject = QAService._normalize_text(subject_text) if subject_text else ""
        normalized_lowered = QAService._normalize_text(normalized)
        if normalized_subject:
            subject_index = normalized_lowered.find(normalized_subject)
            if subject_index >= 0:
                normalized = normalized[subject_index:]
                lowered = normalized.lower()

        cue_patterns = (
            "bunlar:",
            "bunlar",
            "sunlar:",
            "sunlar",
            "şunlar:",
            "şunlar",
            "listesi:",
            "listesi",
        )
        for cue in cue_patterns:
            cue_match = re.search(re.escape(cue), normalized, flags=re.IGNORECASE)
            if cue_match:
                normalized = normalized[cue_match.end():]
                section_break = re.search(r"\s+(?:Şekil|Sekil|[2-9]\.\d+)\b", normalized, flags=re.IGNORECASE)
                if section_break:
                    normalized = normalized[: section_break.start()]
                lowered = normalized.lower()
                break

        first_numbered_match = re.search(r"\d+[.)-]?\s*", normalized)
        header_text = normalized[: first_numbered_match.start()].strip() if first_numbered_match else normalized[:120].strip()

        lines = [line.strip(" \t-•") for line in normalized.splitlines() if line.strip()]
        numbered_line_items: list[str] = []
        for line in lines:
            match = re.match(r"^\d+[.)-]?\s*(.+)$", line)
            if match:
                candidate = QAService._clean_list_item(match.group(1).strip(" ;:."))
                if len(candidate) <= 120:
                    numbered_line_items.append(candidate)
        if len(numbered_line_items) >= 2:
            return numbered_line_items, header_text

        compact = " ".join(normalized.split())
        bullet_segments = [
            QAService._clean_list_item(item.strip(" ;:."))
            for item in re.split(r"\s+[•-]\s+", compact)
            if item.strip()
        ]
        if len(bullet_segments) >= 3:
            return bullet_segments[1:], header_text

        numbered_inline_items = [
            QAService._clean_list_item(match.group(1).strip(" ;:."))
            for match in re.finditer(r"(?:^|\s)\d+[.)-]?\s*([^0-9].*?)(?=(?:\s+\d+[.)-]?\s)|$)", compact)
        ]
        numbered_inline_items = [item for item in numbered_inline_items if len(item) <= 120]
        if len(numbered_inline_items) >= 2:
            return numbered_inline_items, header_text

        return [], header_text

    def _sentence_score(
        self,
        question_tokens: list[str],
        question: str,
        sentence: str,
        context: dict,
        question_profile: dict,
    ) -> float:
        sentence_lower = sentence.casefold()
        unique_tokens = list(dict.fromkeys(token for token in question_tokens if token))
        overlap = sum(1 for token in unique_tokens if self._normalize_text(token) in self._normalize_text(sentence_lower))
        overlap_ratio = overlap / len(unique_tokens) if unique_tokens else 0.0
        has_number = any(char.isdigit() for char in sentence)
        numeric_bonus = 0.25 if has_number and question_profile["expects_number"] else 0.0
        exact_phrase_bonus = 0.3 if self._normalize_text(question) in self._normalize_text(sentence_lower) else 0.0
        keyword_hint_bonus = 0.15 if question_profile["wants_reason"] and any(
            clue in self._normalize_text(sentence_lower) for clue in ("nedeni", "sebebi", "cunku", "sonuc", "degerlendirme")
        ) else 0.0
        purpose_bonus = 0.35 if question_profile["wants_purpose"] and any(
            clue in self._normalize_text(sentence_lower) for clue in ("amac", "temel amac", "hedef", "kapsam")
        ) else 0.0
        normalized_sentence = self._normalize_text(sentence_lower)
        measurement_terms = ("olcul", "ivme", "direksiyon", "side slip", "kayma")
        measurement_match_count = sum(1 for clue in measurement_terms if clue in normalized_sentence)
        measurement_bonus = min(measurement_match_count * 0.22, 0.75) if question_profile["wants_measurement"] else 0.0
        label_bonus = 0.12 if question_profile["wants_name"] and any(
            clue in normalized_sentence for clue in ("ad", "isim", "baslik", "bolum")
        ) else 0.0
        retrieval_bonus = (
            max(
                float(context["result"].get("combined_score", 0.0) or 0.0),
                float(context["result"].get("semantic_score", 0.0) or 0.0),
                float(context["result"].get("keyword_score", 0.0) or 0.0),
            ) * 0.22
        )
        scope_bonus = 0.14 if context["scope"] == "section" else 0.0
        section_bonus = context["section_match"] * 0.2
        short_sentence_bonus = 0.08 if 35 <= len(sentence) <= 220 else 0.0
        heading_like_penalty = 0.45 if len(sentence) < 90 and sentence.rstrip().endswith(":") else 0.0
        measurement_noise_penalty = (
            0.35
            if question_profile["wants_measurement"]
            and "degerlendirme" in normalized_sentence
            and measurement_match_count == 0
            else 0.0
        )
        low_overlap_penalty = 0.25 if overlap_ratio < self.MIN_TOKEN_OVERLAP_RATIO else 0.0
        length_penalty = max(len(sentence) - 320, 0) / 900
        rank_bonus = max(0.15 - context["rank"] * 0.03, 0.0)
        return (
            overlap_ratio
            + numeric_bonus
            + exact_phrase_bonus
            + keyword_hint_bonus
            + purpose_bonus
            + measurement_bonus
            + label_bonus
            + retrieval_bonus
            + scope_bonus
            + section_bonus
            + short_sentence_bonus
            + rank_bonus
            - low_overlap_penalty
            - heading_like_penalty
            - measurement_noise_penalty
            - length_penalty
        )

    def _list_score(self, items: list[str], header_text: str, context: dict) -> float:
        combined_text = self._normalize_text(" ".join(items))
        subject_tokens = context["question_profile"]["subject_tokens"]
        unique_tokens = list(dict.fromkeys(token for token in subject_tokens if token))
        overlap = sum(1 for token in unique_tokens if self._normalize_text(token) in combined_text)
        overlap_ratio = overlap / len(unique_tokens) if unique_tokens else 0.0
        subject_aliases = context["question_profile"]["subject_aliases"]
        normalized_context = self._normalize_text(context["text"])
        subject_bonus = 0.75 if self._contains_any_alias(normalized_context, subject_aliases) else -0.3
        topic_focus_terms = {
            token
            for token in context["question_profile"]["subject_tokens"]
            if token in {"ekipman", "ekipmanlari", "enstrumantasyon", "parkur", "parkurlari", "guzergah", "yol", "yollar"}
        }
        topic_focus_bonus = 0.85 if topic_focus_terms and any(token in normalized_context for token in topic_focus_terms) else 0.0
        normalized_header = self._normalize_text(header_text)
        header_overlap = sum(1 for token in unique_tokens if self._normalize_text(token) in normalized_header)
        header_overlap_ratio = header_overlap / len(unique_tokens) if unique_tokens else 0.0
        header_subject_bonus = 0.9 if self._contains_any_alias(normalized_header, subject_aliases) else 0.0
        retrieval_bonus = (
            max(
                float(context["result"].get("combined_score", 0.0) or 0.0),
                float(context["result"].get("semantic_score", 0.0) or 0.0),
                float(context["result"].get("keyword_score", 0.0) or 0.0),
            ) * 0.24
        )
        item_count_bonus = min(len(items), 6) * 0.05
        scope_bonus = 0.18 if context["scope"] == "section" else 0.0
        section_bonus = context["section_match"] * 0.24
        rank_bonus = max(0.12 - context["rank"] * 0.025, 0.0)
        average_length = sum(len(item) for item in items) / max(len(items), 1)
        compact_bonus = 0.28 if average_length <= 28 else 0.14 if average_length <= 48 else -0.18
        colon_penalty = sum(0.1 for item in items if ":" in item)
        long_item_penalty = sum(0.12 for item in items if len(item) > 70)
        visual_index_penalty = sum(
            0.4
            for item in items
            if any(marker in self._normalize_text(item) for marker in ("gorsel", "grafik", "lokasyon"))
        )
        junk_item_penalty = sum(0.45 for item in items if self._normalize_text(item) in {"/", "page"})
        return (
            overlap_ratio
            + subject_bonus
            + topic_focus_bonus
            + header_overlap_ratio * 0.9
            + header_subject_bonus
            + retrieval_bonus
            + item_count_bonus
            + scope_bonus
            + section_bonus
            + rank_bonus
            + compact_bonus
            - colon_penalty
            - long_item_penalty
            - visual_index_penalty
            - junk_item_penalty
        )

    @staticmethod
    def _question_profile(question: str) -> dict:
        lowered = QAService._normalize_text(question)
        list_terms = (
            "nelerdir",
            "hangileri",
            "listesi",
            "maddeler",
            "parkurlar",
            "parkurlari",
            "guzergah",
            "guzergahlar",
            "yollardan",
            "yollarda",
            "yollar",
            "adlari",
            "asamalar",
            "ekipman",
            "ekipmanlari",
        )
        raw_tokens = re.findall(r"\w+", lowered)
        raw_token_set = set(raw_tokens)
        wants_list = any(token in raw_token_set for token in list_terms) or (
            "hangi" in raw_token_set
            and any(token in raw_token_set for token in ("yol", "yollar", "parkur", "guzergah", "senaryo", "kosul", "ekipman", "ekipmanlari"))
        )
        filler_tokens = {
            "nelerdir",
            "hangileri",
            "hangisi",
            "hangi",
            "nereler",
            "nerelerde",
            "nereden",
            "listesi",
            "maddeler",
            "nedir",
            "neler",
            "ve",
            "veya",
        }
        subject_tokens = [token for token in raw_tokens if token not in filler_tokens and len(token) >= 3]
        expanded_subject_tokens = QAService._expand_tokens(subject_tokens)
        subject_aliases = QAService._build_subject_aliases(subject_tokens)
        subject_search_terms = list(
            dict.fromkeys(
                expanded_subject_tokens
                + [token[:5] for token in expanded_subject_tokens if len(token) >= 6]
            )
        )
        return {
            "expects_number": any(token in raw_token_set for token in ("kac", "maksimum", "minimum", "mpa", "mm", "oran")),
            "wants_reason": any(token in lowered for token in ("neden", "niye", "sebep", "gerekce")),
            "wants_purpose": any(token in lowered for token in ("amac", "hedef", "kapsam")),
            "wants_measurement": any(
                token in raw_token_set
                for token in ("olcul", "olculmektedir", "olculecektir", "deger", "degerler")
            ),
            "wants_name": any(token in lowered for token in ("hangi", "hangisi", "ad", "isim", "baslik")),
            "wants_list": wants_list,
            "subject_tokens": expanded_subject_tokens,
            "subject_search_terms": subject_search_terms,
            "subject_text": " ".join(subject_tokens).strip(),
            "subject_aliases": subject_aliases,
        }

    @staticmethod
    def _normalize_confidence(score: float) -> float:
        if score <= 0.0:
            return 0.0
        return max(0.0, min(score / 1.4, 1.0))

    @staticmethod
    def _section_overlap(question_tokens: list[str], section_title: str | None) -> float:
        if not section_title:
            return 0.0
        return QAService._text_overlap(question_tokens, section_title)

    @staticmethod
    def _text_overlap(tokens: list[str], text: str | None) -> float:
        if not text:
            return 0.0
        unique_tokens = list(dict.fromkeys(token for token in tokens if token))
        if not unique_tokens:
            return 0.0
        normalized_text = QAService._normalize_text(text)
        words = re.findall(r"\w+", normalized_text)
        overlap = 0
        for token in unique_tokens:
            normalized_token = QAService._normalize_text(token)
            if normalized_token in normalized_text:
                overlap += 1
                continue
            prefix = normalized_token[:5] if len(normalized_token) >= 5 else normalized_token
            if prefix and any(word.startswith(prefix) or prefix.startswith(word[:5]) for word in words if len(word) >= min(len(prefix), 3)):
                overlap += 1
        return overlap / len(unique_tokens)

    @classmethod
    def _expand_tokens(cls, tokens: list[str]) -> list[str]:
        expanded: list[str] = []
        for token in tokens:
            variants = cls.TOKEN_SYNONYMS.get(token, {token})
            for variant in variants:
                if variant not in expanded:
                    expanded.append(variant)
        return expanded

    @classmethod
    def _build_subject_aliases(cls, tokens: list[str]) -> list[str]:
        aliases: list[str] = []
        base = " ".join(tokens).strip()
        if base:
            aliases.append(base)
        for index, token in enumerate(tokens):
            variants = cls.TOKEN_SYNONYMS.get(token, {token})
            for variant in variants:
                if variant == token:
                    continue
                variant_tokens = list(tokens)
                variant_tokens[index] = variant
                alias = " ".join(variant_tokens).strip()
                if alias and alias not in aliases:
                    aliases.append(alias)
        return [cls._normalize_text(alias) for alias in aliases]

    @staticmethod
    def _contains_any_alias(text: str, aliases: list[str]) -> bool:
        return any(alias and alias in text for alias in aliases)

    @classmethod
    def _question_variants(cls, question: str, question_profile: dict) -> list[str]:
        variants = [question]
        subject_text = question_profile["subject_text"]
        normalized_question = cls._normalize_text(question)
        for alias in question_profile["subject_aliases"]:
            if not alias or alias == cls._normalize_text(subject_text):
                continue
            if subject_text and cls._normalize_text(subject_text) in normalized_question:
                candidate = re.sub(
                    re.escape(subject_text),
                    alias,
                    normalized_question,
                    count=1,
                )
                candidate = " ".join(candidate.split())
                if candidate and candidate not in variants:
                    variants.append(candidate)
        return variants[:4]

    @staticmethod
    def _normalize_text(text: str) -> str:
        lowered = text.casefold()
        translation = str.maketrans({
            "ı": "i",
            "ğ": "g",
            "ü": "u",
            "ş": "s",
            "ö": "o",
            "ç": "c",
        })
        return lowered.translate(translation)

    @staticmethod
    def _clean_list_item(item: str) -> str:
        trimmed = item.strip(" ;:.")
        normalized = QAService._normalize_text(trimmed)
        markers = (
            " sekil",
            " ekil",
            " analiz dosyasi",
            " page ",
            " hazirlayan",
            " talep eden",
            " sekil-",
            " test hazirligi",
            " test bilgisi",
            " sonuc",
            " test kosullari",
            " test kosullar",
        )
        cut_positions = []
        for marker in markers:
            pos = normalized.find(marker)
            if pos > 0:
                cut_positions.append(pos)
        if cut_positions:
            trimmed = trimmed[: min(cut_positions)].strip(" ;:.")
        trimmed = re.sub(r"\s+\d+[.)-]?$", "", trimmed).strip(" ;:.")
        return trimmed
