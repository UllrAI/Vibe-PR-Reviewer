import logging

from fastapi import FastAPI, Request, Depends, BackgroundTasks
from starlette.concurrency import run_in_threadpool

from core.config import settings, setup_logging
from utils.security import verify_github_signature
from services.webhook_service import handle_webhook_event

# Setup logging
setup_logging()

app = FastAPI(
    title="PR Review Bot",
    version="1.0.0",
    description="A bot that uses AI to review Pull Requests on GitHub."
)

logger = logging.getLogger("pr_review_bot")

async def get_raw_body(request: Request):
    return await request.body()

@app.on_event("startup")
async def startup_event():
    logger.info("Application startup...")
    logger.info(f"Log level set to: {settings.LOG_LEVEL}")


@app.get("/", tags=["General"])
async def read_root():
    """Health check endpoint."""
    return {"status": "alive"}


@app.post("/webhook", tags=["GitHub"])
async def github_webhook(request: Request, background_tasks: BackgroundTasks, raw_body: bytes = Depends(get_raw_body)):
    """Endpoint to receive GitHub webhooks."""
    await run_in_threadpool(verify_github_signature, request, raw_body)
    
    payload = await request.json()
    event_type = request.headers.get("X-GitHub-Event")
    
    logger.info(f"Received GitHub event: {event_type}")
    background_tasks.add_task(handle_webhook_event, event_type, payload)
    
    return {"status": "accepted"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)