"""
WK Aircond Service - WhatsApp AI Chatbot
Auto-replies to customer inquiries using Claude AI
"""

import json
import logging
import httpx
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse, JSONResponse
from contextlib import asynccontextmanager

from config import settings
from ai_handler import AIHandler
from whatsapp_client import WhatsAppClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

ai_handler = AIHandler()
wa_client = WhatsAppClient()

# Store last few webhook payloads for debugging
_debug_log = []

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 WK Aircond Bot starting up...")
    try:
        settings.validate_required()
        logger.info("✅ All required environment variables are set")
        logger.info(f"📱 Phone Number ID: {settings.WHATSAPP_PHONE_NUMBER_ID}")
        logger.info(f"🤖 AI Model: {settings.AI_MODEL}")
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
    logger.info(f"🔐 Verify request — mode={hub_mode}, token={hub_verify_token}")
    if hub_mode == "subscribe" and hub_verify_token == settings.WHATSAPP_VERIFY_TOKEN:
        logger.info("✅ Webhook verified successfully")
        return PlainTextResponse(hub_challenge)
    logger.warning(f"❌ Webhook verification FAILED — expected token: {settings.WHATSAPP_VERIFY_TOKEN}")
    raise HTTPException(status_code=403, detail="Verification failed")


@app.post("/webhook")
async def receive_webhook(request: Request):
    """Handle incoming WhatsApp messages"""
    try:
        body = await request.json()
        logger.info(f"📨 Incoming webhook:\n{json.dumps(body, indent=2)}")

        # Save for debug endpoint (keep last 10)
        _debug_log.append(body)
        if len(_debug_log) > 10:
            _debug_log.pop(0)

        entry = body.get("entry", [])
        if not entry:
            logger.info("ℹ️  Webhook has no entry (likely a status update, ignoring)")
            return {"status": "ok"}

        for e in entry:
            for change in e.get("changes", []):
                value = change.get("value", {})

                # Skip status updates (delivery receipts, read receipts)
                if "statuses" in value:
                    logger.info("ℹ️  Received status update, skipping")
                    continue

                messages = value.get("messages", [])
                if not messages:
                    logger.info("ℹ️  No messages in this change")
                    continue

                for msg in messages:
                    msg_type = msg.get("type")
                    from_number = msg.get("from")
                    msg_id = msg.get("id")

                    logger.info(f"📩 Message type={msg_type} from={from_number} id={msg_id}")

                    if msg_type == "text":
                        user_text = msg["text"]["body"]
                        logger.info(f"💬 Text: {user_text}")

                        # Mark as read (shows blue ticks)
                        await wa_client.mark_as_read(msg_id)

                        # Get AI response
                        logger.info("🤖 Getting AI response...")
                        reply = await ai_handler.get_response(from_number, user_text)
                        logger.info(f"✍️  AI reply (preview): {reply[:100]}...")

                        # Send reply
                        success = await wa_client.send_message(from_number, reply)
                        if success:
                            logger.info(f"✅ Reply sent to {from_number}")
                        else:
                            logger.error(f"❌ Failed to send reply to {from_number}")

                    elif msg_type in ("image", "audio", "video", "document"):
                        logger.info(f"📎 Received {msg_type} — sending fallback message")
                        await wa_client.send_message(
                            from_number,
                            "Terima kasih! Sila hubungi kami terus untuk pertanyaan dengan fail/gambar. 😊\n\n"
                            "Thank you! Please contact us directly for inquiries with files/images."
                        )

                    elif msg_type == "button":
                        button_text = msg.get("button", {}).get("text", "")
                        logger.info(f"🔘 Button press: {button_text}")
                        reply = await ai_handler.get_response(from_number, button_text)
                        await wa_client.send_message(from_number, reply)

                    else:
                        logger.info(f"⚠️  Unhandled message type: {msg_type}")

    except json.JSONDecodeError:
        logger.error("❌ Failed to parse webhook body as JSON")
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)

    # Always return 200 OK to Meta, otherwise Meta will retry indefinitely
    return {"status": "ok"}


@app.get("/health")
async def health():
    """Health check — also shows config status"""
    config_ok = bool(settings.WHATSAPP_ACCESS_TOKEN and settings.ANTHROPIC_API_KEY)
    return {
        "status": "healthy",
        "bot": "WK Aircond Service WhatsApp Bot",
        "config_ok": config_ok,
        "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID or "NOT SET",
        "ai_model": settings.AI_MODEL,
        "verify_token": settings.WHATSAPP_VERIFY_TOKEN,
    }


@app.get("/debug/logs")
async def debug_logs():
    """Show last received webhook payloads — useful for troubleshooting"""
    return JSONResponse({
        "count": len(_debug_log),
        "payloads": _debug_log,
    })


@app.get("/debug/test-send")
async def test_send(to: str, msg: str = "Hello from WK Aircond Bot! Test message ✅"):
    """
    Test sending a WhatsApp message directly.
    Usage: /debug/test-send?to=601XXXXXXXX&msg=hello
    """
    logger.info(f"🧪 Test send to {to}: {msg}")
    success = await wa_client.send_message(to, msg)
    return {
        "success": success,
        "to": to,
        "message": msg,
        "phone_number_id": settings.WHATSAPP_PHONE_NUMBER_ID,
        "token_set": bool(settings.WHATSAPP_ACCESS_TOKEN),
    }


@app.get("/")
async def root():
    return {
        "name": "WK Aircond Service WhatsApp Bot",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "webhook": "/webhook",
            "debug_logs": "/debug/logs",
            "test_send": "/debug/test-send?to=601XXXXXXXX",
        }
    }