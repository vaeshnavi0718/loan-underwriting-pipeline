import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api import routes_applications, routes_review
from app.logging_config import setup_logging

setup_logging()
logger = logging.getLogger("main")

app = FastAPI(title="Loan Underwriting Pipeline (synthetic data only)")

app.include_router(routes_applications.router)
app.include_router(routes_review.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
def on_startup():
    logger.info("Loan underwriting pipeline starting up.")


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
