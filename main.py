"""
WK Aircond Service - WhatsApp AI Chatbot
Auto-replies to customer inquiries using Claude AI
"""

import json
import logging
import httpx
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from contextlib import asynccontextmanager

from config import settings
from ai_handler import AIHandler
from whatsapp_client import WhatsAppClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ai_handler = AIHandler()
wa_client = WhatsAppClient()

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 WK Aircond Bot starting up...")
    try:
        settings.validate_required()
        logger.info("✅ All required environment variables are set")
    except ValueError as e:
        logger.error(f"⚠️  CONFIG WARNING: {e}")
        logger.error("Bot will start but WhatsApp/AI features won't work until env vars are set in Railway dashboard")
    yield
    logger.info("👋 WK Aircond Bot shutting down...")

app = FastAPI(title="WK Aircond WhatsApp Bot", lifespan=lifespan)


@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    """WhatsApp webhook verification"""
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully")
        return PlainTextResponse(hub_challenge)
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def receive_webhook(request: Request):
    """Handle incoming WhatsApp messages"""
    try:
        body = await request.json()
        logger.info(f"📨 Incoming webhook: {json.dumps(body, indent=2)}")

        entry = body.get("entry", [])
        if not entry:
            return {"status": "ok"}

        for e in entry:
            for change in e.get("changes", []):
                value = change.get("value", {})
                messages = value.get("messages", [])

                for msg in messages:
                    msg_type = msg.get("type")
                    from_number = msg.get("from")
                    msg_id = msg.get("id")

                    if msg_type == "text":
                        user_text = msg["text"]["body"]
                        logger.info(f"💬 Message from {from_number}: {user_text}")

                        # Mark as read
                        await wa_client.mark_as_read(msg_id)

                        # Send typing indicator
                        await wa_client.send_typing(from_number)

                        # Get AI response
                        reply = await ai_handler.get_response(from_number, user_text)

                        # Send reply
                        await wa_client.send_message(from_number, reply)

                    elif msg_type in ("image", "audio", "video", "document"):
                        await wa_client.send_message(
                            from_number,
                            "Terima kasih! Sila hubungi kami terus untuk pertanyaan dengan fail/gambar. 😊\n\n"
                            "Thank you! Please contact us directly for inquiries with files/images."
                        )

    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)

    return {"status": "ok"}


@app.get("/health")
async def health():
    return {"status": "healthy", "bot": "WK Aircond Service WhatsApp Bot"}


@app.get("/")
async def root():
    return {
        "name": "WK Aircond Service WhatsApp Bot",
        "status": "running",
        "endpoints": ["/webhook", "/health"]
    }