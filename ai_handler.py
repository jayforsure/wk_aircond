""" AI Handler - Uses Claude to generate responses for WK Aircond Service """

import json
import logging
import redis.asyncio as redis
import httpx
from config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a friendly and professional customer service assistant for WK Aircond Service, a Malaysian air conditioning service company.

## About WK Aircond Service:
- **Company**: WK Aircond Service (Registered in Malaysia since 2018, Reg No: 002814798U)
- **Services**: Air conditioner installation, servicing, repair, chemical cleaning, gas top-up, water leakage fix
- **Coverage**: Selangor, Kuala Lumpur, and surrounding Klang Valley areas
- **Brands Serviced**: All brands - Daikin, Panasonic, Mitsubishi, Midia, Gree, Sharp, York, etc.
- **Unit Types**: Split unit, cassette, ceiling, inverter, non-inverter (residential & commercial)

## Service & Approximate Pricing (RM):
1. Basic Servicing (1 unit): RM 50 - RM 80
2. Chemical Wash (1 unit): RM 100 - RM 150
3. Gas Top-Up (R32/R410A): RM 120 - RM 200
4. Aircond Installation: RM 300 (depends on HP & location)
5. Repair / Diagnostic: RM 90 (parts extra)
6. Water Leakage Fix: RM 80 - RM 150

*Prices vary based on unit size (HP), brand, and location. Final price confirmed on-site.*

## Booking & Contact:
- Customers should WhatsApp us to book an appointment
- We collect: name, address, type of service needed, preferred date/time
- Operating hours: Monday-Saturday, 8:30 AM - 6.00 PM
- Emergency service available (addiotional charges may apply)

## How to Respond:
1. Reply in the **same language** the customer uses (Malay/English/mixed Manglish is fine)
2. Be warm, helpful and concise
3. For bookings: collect name, address, service type, and preferred schedule
4. For pricing: give estimate but note final price confirmed on-site
5. For technical issues: ask for symptoms, then advise or recommend a technician visit
6. If customer asks something outside your knowledge, say you'll check with the team
7. End responses with a helpful follow-up question when appropriate
8. Use emojis sparingly for a friendly feel 😊
9. Never make up information - if unsure, say "I'll check with out team for you"

# Common Customer Issues to Help With:
- Aircond not cooling / blowing warm air -> likely gas leak or dirty filter
- Water dripping from indoor unit -> blocked drain pipe
- Strange noise -> loose parts or debris in fan
- Aircond not turning on -> electrical issue or remote problem
- High electricity bill -> dirty filter or refrigerant issue
- Moudly/bad smell -> needs chemical cleaning
"""

# Max messages to keep in conversation history per user
MAX_HISTORY = 20


class AIHandler:
    def __init__(self):
        self.redis_client = None
        self._init_redis()

    def _init_redis(self):
        try:
            self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses= True)
            logger.info("✅ Redis connected for conversation history")
        except Exception as e:
            logger.warning(f"⚠️ Redis not available, using in-memory fallback: {e}")
            self.redis_client = None
            self._memory_store = {}

    async def get_history(self, user_id: str) -> list:
        key = f"wk_aircond:chat:{user_id}"
        try:
            if self.redis_client:
                data = await self.redis_client.get(key)
                return json.loads(data) if data else []
            else:
                return self._memory_store.get(key, [])
        except Exception as e:
            logger.error(f"Error getting history: {e}")
            return []
        
    async def save_history(self, user_id: str, history: list):
        key = f"wk_aircond:chat:{user_id}"
        # Keep only last N messages
        if len(history) > MAX_HISTORY:
            history = history[-MAX_HISTORY:]
        try:
            if self.redis_client:
                await self.redis_client.setex(key, 86400 * 7, json.dumps(history)) # 7 days TTL
            else:
                self._memory_store[key] = history
        except Exception as e:
            logger.error(f"Error saving history: {e}")
        
    async def get_response(self, user_id: str, user_message: str) -> str:
        """ Get AI response using Claude API """
        history = await self.get_history(user_id)

        # Add new user message
        history.append({"role": "user", "content": user_message})

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.anthropic.com/v1/messages",
                    headers={
                        "x-api-key": settings.ANTHROPIC_API_KEY,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json={
                        "model": settings.AI_MODEL,
                        "max_tokens": settings.AI_MAX_TOKENS,
                        "system": SYSTEM_PROMPT,
                        "messages": history,
                    },
                )
                response.raise_for_status()
                data = response.json()
                ai_reply = data["content"][0]["text"]
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Anthropic API error: {e.response.text}")
            ai_reply = (
                "Maaf, sistem kami mengalami masalah teknikal. Sila cuba lagi sebenter. 🙏\n\n"
                "Sorry, our system is experiencing a technical issue. Please try again shortly."
            )
        except Exception as e:
            logger.error(f"AI response error: {e}")
            ai_reply = (
                "Maaf, terdapat ralat. Untuk pertanyaan segera, sila hubungi kami terus. 😊\n\n"
                "Sorry, there was an error. For urgent inquiries, please contact us directly."
            )
        
        # Save updated history (with assistant reply)
        history.append({"role": "assistant", "content": ai_reply})
        await self.save_history(user_id, history)

        return ai_reply