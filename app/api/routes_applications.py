"""Routes for creating applications and uploading documents. This is where
the Harness is kicked off after documents are submitted."""
import logging
import os
import uuid

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.harness import orchestrator
from app.harness.state import ApplicationState

logger = logging.getLogger("api.applications")
router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))

UPLOAD_ROOT = os.path.join(os.path.dirname(__file__), "..", "..", "data", "uploads")
os.makedirs(UPLOAD_ROOT, exist_ok=True)

DOC_FIELD_NAMES = ["pay_stub", "bank_statement", "credit_report", "id_document"]


@router.get("/")
def index(request: Request):
    applications = sorted(ApplicationState.list_all(), key=lambda s: s.application_id)
    return templates.TemplateResponse("index.html", {"request": request, "applications": applications})


async def _save_uploaded_docs(application_id: str, files: dict[str, UploadFile | None]) -> dict[str, str]:
    app_dir = os.path.join(UPLOAD_ROOT, application_id)
    os.makedirs(app_dir, exist_ok=True)
    saved: dict[str, str] = {}
    for doc_type, upload in files.items():
        if upload is None or not upload.filename:
            continue
        dest = os.path.join(app_dir, f"{doc_type}.pdf")
        content = await upload.read()
        with open(dest, "wb") as f:
            f.write(content)
        saved[doc_type] = dest
    return saved


@router.post("/applications")
async def create_application(
    applicant_name: str = Form(...),
    requested_amount: float = Form(...),
    loan_purpose: str = Form(...),
    employment_status: str = Form(...),
    pay_stub: UploadFile | None = None,
    bank_statement: UploadFile | None = None,
    credit_report: UploadFile | None = None,
    id_document: UploadFile | None = None,
):
    application_id = f"APP-WEB-{uuid.uuid4().hex[:8].upper()}"
    application_fields = {
        "application_id": application_id,
        "applicant_name": applicant_name,
        "requested_amount": requested_amount,
        "loan_purpose": loan_purpose,
        "employment_status": employment_status,
    }
    orchestrator.create_application(application_id, application_fields)
    logger.info("Created application %s for %s", application_id, applicant_name)

    docs = await _save_uploaded_docs(
        application_id,
        {
            "pay_stub": pay_stub,
            "bank_statement": bank_statement,
            "credit_report": credit_report,
            "id_document": id_document,
        },
    )
    orchestrator.run_pipeline(application_id, new_document_paths=docs)
    return RedirectResponse(url=f"/applications/{application_id}", status_code=303)


@router.get("/applications/{application_id}")
def application_detail(request: Request, application_id: str):
    state = ApplicationState.load(application_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return templates.TemplateResponse(
        "application_detail.html", {"request": request, "state": state, "doc_fields": DOC_FIELD_NAMES}
    )


@router.post("/applications/{application_id}/documents")
async def upload_more_documents(
    application_id: str,
    pay_stub: UploadFile | None = None,
    bank_statement: UploadFile | None = None,
    credit_report: UploadFile | None = None,
    id_document: UploadFile | None = None,
):
    state = ApplicationState.load(application_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Application not found")

    docs = await _save_uploaded_docs(
        application_id,
        {
            "pay_stub": pay_stub,
            "bank_statement": bank_statement,
            "credit_report": credit_report,
            "id_document": id_document,
        },
    )
    if not docs:
        raise HTTPException(status_code=400, detail="No documents provided")

    orchestrator.run_pipeline(application_id, new_document_paths=docs)
    return RedirectResponse(url=f"/applications/{application_id}", status_code=303)
