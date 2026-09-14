"""Human checkpoint routes. This module is the only place in the codebase
allowed to trigger a final APPROVED/DENIED decision, and it only does so by
calling orchestrator.apply_human_decision with a decision the human
submitted through the UI -- no agent or LLM is involved."""
import logging
import os

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from app.harness import orchestrator
from app.harness.state import ApplicationState, Status

logger = logging.getLogger("api.review")
router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "..", "templates"))


@router.get("/applications/{application_id}/review")
def review_page(request: Request, application_id: str):
    state = ApplicationState.load(application_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Application not found")
    if state.status != Status.AWAITING_HUMAN_DECISION:
        return RedirectResponse(url=f"/applications/{application_id}")
    return templates.TemplateResponse("review.html", {"request": request, "state": state})


@router.post("/applications/{application_id}/decision")
def submit_decision(
    application_id: str,
    decision: str = Form(...),
    notes: str = Form(""),
    requested_documents: list[str] = Form(default=[]),
):
    state = ApplicationState.load(application_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Application not found")

    logger.info("Human decision for %s: %s", application_id, decision)
    orchestrator.apply_human_decision(
        application_id, decision, notes=notes, requested_documents=requested_documents
    )
    return RedirectResponse(url=f"/applications/{application_id}", status_code=303)
