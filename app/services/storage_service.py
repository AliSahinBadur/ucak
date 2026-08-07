from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db.models import Document
from .document_path_service import resolve_document_file_path


class StorageService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def check_storage(self) -> dict:
        documents = self.session.scalars(select(Document).order_by(Document.id.asc())).all()
        issues: list[dict] = []

        for document in documents:
            if resolve_document_file_path(document.file_path) is None:
                issues.append(
                    {
                        "document_id": document.id,
                        "file_name": document.file_name,
                        "file_path": document.file_path,
                        "issue": "missing_file",
                    }
                )

        return {
            "total_documents": len(documents),
            "healthy_documents": len(documents) - len(issues),
            "missing_file_count": len(issues),
            "issues": issues,
        }
