"""
Shared application state owned by the Agent Harness.

Persisted as a small set of files per application under
data/state/{application_id}/ -- one file per category of data
(core record, extracted_information, enrichment_results, risk_assessment,
review_report, execution_history). This keeps the full audit trail on disk
without any of it needing to be rendered in the UI.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger("harness")

STATE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "state")
os.makedirs(STATE_DIR, exist_ok=True)

_locks: dict[str, threading.Lock] = {}
_locks_guard = threading.Lock()


def _lock_for(application_id: str) -> threading.Lock:
    with _locks_guard:
        if application_id not in _locks:
            _locks[application_id] = threading.Lock()
        return _locks[application_id]


def _write_json(path: str, data: Any) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, default=str)


def _read_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path) as f:
        return json.load(f)


class Status(StrEnum):
    CREATED = "CREATED"
    IN_PROGRESS = "IN_PROGRESS"
    NEEDS_DOCUMENTATION = "NEEDS_DOCUMENTATION"
    AWAITING_HUMAN_DECISION = "AWAITING_HUMAN_DECISION"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    ERROR = "ERROR"


class Step(StrEnum):
    INTAKE = "INTAKE"
    DOCUMENT_EXTRACTION = "DOCUMENT_EXTRACTION"
    ENRICHMENT = "ENRICHMENT"
    RISK_ANALYSIS = "RISK_ANALYSIS"
    REVIEW = "REVIEW"
    HUMAN_CHECKPOINT = "HUMAN_CHECKPOINT"
    DONE = "DONE"


class LogEntry(BaseModel):
    timestamp: str
    step: str
    event: str
    detail: str = ""


class ApplicationState(BaseModel):
    application_id: str
    current_step: Step = Step.INTAKE
    status: Status = Status.CREATED

    uploaded_documents: dict[str, str] = Field(default_factory=dict)  # doc_type -> filename
    extracted_information: dict[str, Any] = Field(default_factory=dict)
    enrichment_results: dict[str, Any] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)
    risk_assessment: dict[str, Any] = Field(default_factory=dict)
    review_report: dict[str, Any] = Field(default_factory=dict)
    human_decision: dict[str, Any] | None = None

    execution_history: list[LogEntry] = Field(default_factory=list)
    retry_counts: dict[str, int] = Field(default_factory=dict)

    def log(self, step: str, event: str, detail: str = "") -> None:
        self.execution_history.append(
            LogEntry(
                timestamp=datetime.now(timezone.utc).isoformat(),
                step=step,
                event=event,
                detail=detail,
            )
        )
        logger.info("[%s] %s %s: %s", self.application_id, step, event, detail)

    def dir_path(self) -> str:
        return os.path.join(STATE_DIR, self.application_id)

    def save(self) -> None:
        with _lock_for(self.application_id):
            app_dir = self.dir_path()
            os.makedirs(app_dir, exist_ok=True)

            core = {
                "application_id": self.application_id,
                "current_step": self.current_step,
                "status": self.status,
                "uploaded_documents": self.uploaded_documents,
                "missing_information": self.missing_information,
                "human_decision": self.human_decision,
                "retry_counts": self.retry_counts,
            }
            _write_json(os.path.join(app_dir, "application.json"), core)
            _write_json(os.path.join(app_dir, "extracted_information.json"), self.extracted_information)
            _write_json(os.path.join(app_dir, "enrichment_results.json"), self.enrichment_results)
            _write_json(os.path.join(app_dir, "risk_assessment.json"), self.risk_assessment)
            _write_json(os.path.join(app_dir, "review_report.json"), self.review_report)
            _write_json(
                os.path.join(app_dir, "execution_history.json"),
                [entry.model_dump() for entry in self.execution_history],
            )

    @classmethod
    def load(cls, application_id: str) -> "ApplicationState | None":
        app_dir = os.path.join(STATE_DIR, application_id)
        core_path = os.path.join(app_dir, "application.json")
        if not os.path.exists(core_path):
            return None
        with _lock_for(application_id):
            core = _read_json(core_path, {})
            history = _read_json(os.path.join(app_dir, "execution_history.json"), [])
            return cls(
                application_id=core.get("application_id", application_id),
                current_step=core.get("current_step", Step.INTAKE),
                status=core.get("status", Status.CREATED),
                uploaded_documents=core.get("uploaded_documents", {}),
                missing_information=core.get("missing_information", []),
                human_decision=core.get("human_decision"),
                retry_counts=core.get("retry_counts", {}),
                extracted_information=_read_json(os.path.join(app_dir, "extracted_information.json"), {}),
                enrichment_results=_read_json(os.path.join(app_dir, "enrichment_results.json"), {}),
                risk_assessment=_read_json(os.path.join(app_dir, "risk_assessment.json"), {}),
                review_report=_read_json(os.path.join(app_dir, "review_report.json"), {}),
                execution_history=[LogEntry(**entry) for entry in history],
            )

    @classmethod
    def load_or_create(cls, application_id: str) -> "ApplicationState":
        existing = cls.load(application_id)
        if existing is not None:
            return existing
        state = cls(application_id=application_id)
        state.log("INTAKE", "STATE_CREATED")
        state.save()
        return state

    @classmethod
    def list_all(cls) -> list["ApplicationState"]:
        states = []
        for name in sorted(os.listdir(STATE_DIR)):
            if os.path.isdir(os.path.join(STATE_DIR, name)):
                state = cls.load(name)
                if state is not None:
                    states.append(state)
        return states
