""" WhatsApp Cloud API Client """

import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)


class WhatsAppClient:
    def __init__(self):
        self.headers= {
            "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }
        self.base_url = settings.whatsapp_api_url

    async def send_message(self, to: str, text: str) -> bool:
        """ Send a text message to a WhatsApp number """
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json=payload,
                )
                res.raise_for_status()
                logger.info(f"✅ Message sent to {to}")
                return True
        except Exception as e:
            logger.error(f"❌ Failed to send message to {to}: {e}")
            return False
    
    async def mark_as_read(self,message_id: str) -> bool:
        """ Mark a message as read (shows double blue ticks)"""
        payload = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json=payload,
                )
                res.raise_for_status()
                return True
        except Exception as e:
            logger.warning(f"Could not mark message as read: {e}")
            return False
        
    async def send_typing(self, to: str) -> bool:
        """ Send typing indicator (not officially supported but works via read receipt timing) """
        # WhatsApp doesn't have a direct typing indicator API
        # The read receipt itself signals to the user that we're processing
        return True
    
    async def send_template(self, to: str, template_name: str, language: str = "en_US") -> bool:
        """ Send a WhatsApp template message (must be pre-approved by Meta) """
        payload = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language},
            },
        }
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.post(
                    f"{self.base_url}/messages",
                    headers=self.headers,
                    json=payload,
                )
                res.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Template send failed: {e}")
            return False