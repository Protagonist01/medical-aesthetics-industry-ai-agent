from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from .models.chat import ChatRequest
from .worker import process_event
from .agents.orchestrator import run_agent

app = FastAPI(title="Medical Aesthetics AI Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"message": "Medical Aesthetics AI Agent API is running"}


@app.post("/api/webhook/{source}")
async def webhook(source: str, request: Request):
    """
    Unified Webhook Ingestion Point (Event-Driven).
    Push payloads to Redis/SQS via Celery immediately.
    """
    try:
        payload = await request.json()

        # Async hand-off to Celery Worker
        task = process_event.delay(event_type=f"{source}_msg", payload=payload)

        return {"status": "queued", "task_id": task.id}
    except Exception as e:
        # Log error but return 200 to generic webhooks sometimes to prevent retries if malformed
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat")
async def chat(request: ChatRequest):
    # LEGACY / DIRECT SYNC MODE (For simple frontend demo)
    try:
        # Convert Pydantic models to dicts for the agent
        messages_dicts = [m.dict() for m in request.messages]
        result = await run_agent(
            messages_dicts, request.source, request.session_id, request.language
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/chat/override")
async def chat_override(request: ChatRequest):
    try:
        # In override mode, we just take the last message (which is the admin's correction)
        # and add it to memory as an assistant message.
        from .agents.memory import memory

        correction = request.messages[-1]
        # Ensure it's marked as assistant
        correction.role = "assistant"

        memory.add_message(request.session_id, correction.dict())

        return {"status": "success", "message": "Override applied"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/cost")
async def get_costs():
    from .services.cost import cost_service

    return cost_service.get_aggregated_costs()


@app.get("/api/analytics")
async def get_analytics():
    """
    Get all dashboard metrics for the RevOps dashboard.
    """
    from .services.analytics import analytics_service

    return analytics_service.get_dashboard_metrics()


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe Webhook Endpoint.
    Handles checkout.session.completed and checkout.session.expired events.
    """
    from .services.booking import handle_stripe_webhook

    payload = await request.body()
    signature = request.headers.get("stripe-signature", "")

    result = await handle_stripe_webhook(payload, signature)

    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message"))

    return result


@app.post("/api/handoff")
async def human_handoff(request: Request):
    """
    Human Handoff Endpoint.
    Called when the AI agent needs to escalate to a human.
    """
    from datetime import datetime

    try:
        payload = await request.json()

        # Log the escalation
        escalation_data = {
            "lead_id": payload.get("lead_id"),
            "reason": payload.get("reason", "Unknown"),
            "conversation_summary": payload.get("summary", ""),
            "priority": payload.get("priority", "normal"),
            "status": "pending",
            "created_at": datetime.now().isoformat(),
        }

        # In production: Send notification to staff (email, Slack, SMS)
        # For now, we just log to console and return success
        print(f"🚨 HUMAN HANDOFF REQUESTED: {escalation_data}")

        return {
            "status": "success",
            "message": "Escalation logged. A team member will reach out shortly.",
            "escalation_id": payload.get("lead_id"),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
