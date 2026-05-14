from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document
from app.ops.schemas import DiagnosticSample, OrphanDetectionSummary
from app.storage import get_storage_service


def _path_if_exists(path_str: str | None) -> Path | None:
    if not path_str:
        return None
    return Path(path_str)


def _sample_append(samples: list[DiagnosticSample], sample: DiagnosticSample, *, limit: int) -> None:
    if len(samples) < limit:
        samples.append(sample)


def _document_paths(document: Document) -> list[Path]:
    paths: list[Path] = []
    for value in (document.last_source_path, document.moved_to_path):
        path = _path_if_exists(value)
        if path is not None:
            paths.append(path)
    return paths


def _storage_artifact_present(document: Document, storage) -> tuple[bool, list[str]]:
    present_references: list[str] = []
    if document.storage_key and storage.has_document(document.storage_key):
        present_references.append(f"storage_key={document.storage_key}")

    for path in _document_paths(document):
        if storage.legacy_path_exists(path):
            present_references.append(f"path={path}")

    return bool(present_references), present_references


def build_orphan_detection_summary(
    session: Session,
    settings,
    *,
    sample_limit: int = 10,
) -> OrphanDetectionSummary:
    storage = get_storage_service(settings)
    documents = session.execute(select(Document).order_by(Document.id.asc())).scalars().all()

    samples: list[DiagnosticSample] = []
    missing_referenced_artifact_count = 0
    retained_missing_source_count = 0
    cleaned_source_still_present_count = 0
    source_expected_without_reference_count = 0

    referenced_storage_keys: set[str] = set()
    for document in documents:
        if document.storage_key:
            referenced_storage_keys.add(document.storage_key)
        for path in _document_paths(document):
            storage_key = storage.storage_key_for_absolute_path(path)
            if storage_key:
                referenced_storage_keys.add(storage_key)

        present, present_references = _storage_artifact_present(document, storage)
        missing_reference_descriptions: list[str] = []
        if document.storage_key and not storage.has_document(document.storage_key):
            missing_reference_descriptions.append(f"storage_key={document.storage_key}")
        for path in _document_paths(document):
            if not storage.legacy_path_exists(path):
                missing_reference_descriptions.append(f"path={path}")

        if missing_reference_descriptions:
            missing_referenced_artifact_count += 1
            _sample_append(
                samples,
                DiagnosticSample(
                    code="missing_referenced_artifact",
                    document_id=document.id,
                    summary="Document references a storage artifact that is missing",
                    details=", ".join(missing_reference_descriptions),
                ),
                limit=sample_limit,
            )

        source_should_exist = bool(document.source_file_present or document.lifecycle_state == "retained")
        has_reference = bool(document.storage_key or document.last_source_path or document.moved_to_path)
        if source_should_exist and not has_reference:
            source_expected_without_reference_count += 1
            _sample_append(
                samples,
                DiagnosticSample(
                    code="source_expected_without_reference",
                    document_id=document.id,
                    summary="Document source should exist but no storage reference is recorded",
                    details=f"lifecycle_state={document.lifecycle_state}",
                ),
                limit=sample_limit,
            )

        if document.lifecycle_state == "retained" and not present:
            retained_missing_source_count += 1
            _sample_append(
                samples,
                DiagnosticSample(
                    code="retained_missing_source",
                    document_id=document.id,
                    summary="Retained document no longer has a readable source artifact",
                    details=f"storage_key={document.storage_key} last_source_path={document.last_source_path}",
                ),
                limit=sample_limit,
            )

        if document.lifecycle_state == "cleaned" and (document.source_file_present or present):
            cleaned_source_still_present_count += 1
            _sample_append(
                samples,
                DiagnosticSample(
                    code="cleaned_source_still_present",
                    document_id=document.id,
                    summary="Cleaned document still appears to have a source artifact",
                    details=", ".join(present_references) if present_references else "source_file_present=True",
                ),
                limit=sample_limit,
            )

    storage_files = sorted(path for path in storage.storage_root.rglob("*") if path.is_file())
    unreferenced_storage_file_count = 0
    for path in storage_files:
        storage_key = storage.storage_key_for_absolute_path(path)
        if storage_key is None or storage_key in referenced_storage_keys:
            continue
        unreferenced_storage_file_count += 1
        _sample_append(
            samples,
            DiagnosticSample(
                code="unreferenced_storage_file",
                storage_key=storage_key,
                path=str(path),
                summary="Storage file exists without any document reference",
            ),
            limit=sample_limit,
        )

    return OrphanDetectionSummary(
        scanned_documents=len(documents),
        scanned_storage_files=len(storage_files),
        sample_limit=sample_limit,
        unreferenced_storage_file_count=unreferenced_storage_file_count,
        missing_referenced_artifact_count=missing_referenced_artifact_count,
        retained_missing_source_count=retained_missing_source_count,
        cleaned_source_still_present_count=cleaned_source_still_present_count,
        source_expected_without_reference_count=source_expected_without_reference_count,
        samples=samples,
    )
