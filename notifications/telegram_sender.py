"""
Telegram Bot Alert Sender

Sends alerts and notifications via Telegram Bot API.
Supports message templates, markdown formatting, and callbacks.
"""

from __future__ import annotations

import asyncio
import aiohttp
from typing import List, Optional, Dict
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TelegramMessage:
    """Telegram message container."""
    text: str
    chat_id: str
    parse_mode: str = "Markdown"
    disable_notification: bool = False
    reply_markup: Optional[Dict] = None


class TelegramBotSender:
    """
    Telegram bot for sending NOC alerts.
    
    Features:
    - Alert notifications
    - Status updates
    - Command responses
    - Inline keyboards for ack
    """
    
    def __init__(self, bot_token: str, default_chat_id: Optional[str] = None):
        self.bot_token = bot_token
        self.default_chat_id = default_chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session
    
    async def send_alert(
        self,
        message: str,
        severity: str = "info",
        chat_id: Optional[str] = None,
        device_id: Optional[str] = None,
        metric_value: Optional[float] = None,
        include_ack_button: bool = True
    ) -> bool:
        """
        Send alert message.
        
        Args:
            message: Alert text
            severity: Alert severity level
            chat_id: Target chat (default if None)
            device_id: Device identifier
            metric_value: Optional metric value
            include_ack_button: Add acknowledge button
        """
        chat_id = chat_id or self.default_chat_id
        if not chat_id:
            logger.error("No chat_id provided")
            return False
        
        # Format message with emoji
        emoji_map = {
            "info": "ℹ️",
            "low": "🟢",
            "medium": "🟡",
            "high": "🟠",
            "critical": "🔴",
            "emergency": "🚨"
        }
        
        emoji = emoji_map.get(severity.lower(), "ℹ️")
        formatted_text = f"{emoji} *{severity.upper()}*\n\n{message}"
        
        if device_id:
            formatted_text += f"\n\n_Device: {device_id}_"
        
        if metric_value is not None:
            formatted_text += f"\n_Value: {metric_value:.2f}_"
        
        # Add buttons
        reply_markup = None
        if include_ack_button and device_id:
            reply_markup = {
                "inline_keyboard": [[
                    {
                        "text": "✅ Acknowledge",
                        "callback_data": f"ack:{device_id}:{severity}"
                    }
                ]]
            }
        
        telegram_msg = TelegramMessage(
            text=formatted_text,
            chat_id=chat_id,
            parse_mode="Markdown",
            reply_markup=reply_markup
        )
        
        return await self._send_message(telegram_msg)
    
    async def send_status_update(
        self,
        summary: Dict,
        chat_id: Optional[str] = None
    ) -> bool:
        """
        Send periodic status update.
        
        Args:
            summary: Health summary dict
            chat_id: Target chat
        """
        chat_id = chat_id or self.default_chat_id
        
        healthy = summary.get("healthy_count", 0)
        warning = summary.get("warning_count", 0)
        critical = summary.get("critical_count", 0)
        
        text = (
            f"📊 *NOC Status Update*\n\n"
            f"🟢 Healthy: {healthy}\n"
            f"🟡 Warning: {warning}\n"
            f"🔴 Critical: {critical}\n\n"
            f"Total Devices: {summary.get('total', 0)}"
        )
        
        if critical > 0:
            text += f"\n\n⚠️ *{critical} devices need immediate attention!*"
        
        msg = TelegramMessage(
            text=text,
            chat_id=chat_id,
            parse_mode="Markdown"
        )
        
        return await self._send_message(msg)
    
    async def send_report(
        self,
        report_text: str,
        chat_id: Optional[str] = None,
        filename: Optional[str] = None
    ) -> bool:
        """
        Send report as text or document.
        
        Args:
            report_text: Report content
            chat_id: Target chat
            filename: Optional filename for document
        """
        chat_id = chat_id or self.default_chat_id
        
        if filename:
            # Send as document
            return await self._send_document(chat_id, report_text, filename)
        else:
            # Split long messages
            max_length = 4000
            if len(report_text) > max_length:
                chunks = [report_text[i:i+max_length] for i in range(0, len(report_text), max_length)]
                for chunk in chunks:
                    msg = TelegramMessage(
                        text=f"📄 *Report (continued)*\n\n```\n{chunk}\n```",
                        chat_id=chat_id,
                        parse_mode="Markdown"
                    )
                    await self._send_message(msg)
                return True
            else:
                msg = TelegramMessage(
                    text=f"📄 *Report*\n\n```\n{report_text}\n```",
                    chat_id=chat_id,
                    parse_mode="Markdown"
                )
                return await self._send_message(msg)
    
    async def _send_message(self, message: TelegramMessage) -> bool:
        """Send message via Telegram API."""
        try:
            session = await self._get_session()
            
            payload = {
                "chat_id": message.chat_id,
                "text": message.text,
                "parse_mode": message.parse_mode,
                "disable_notification": message.disable_notification
            }
            
            if message.reply_markup:
                payload["reply_markup"] = message.reply_markup
            
            async with session.post(
                f"{self.api_url}/sendMessage",
                json=payload
            ) as response:
                if response.status == 200:
                    return True
                else:
                    text = await response.text()
                    logger.error(f"Telegram API error: {response.status} - {text}")
                    return False
                    
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    async def _send_document(
        self,
        chat_id: str,
        content: str,
        filename: str
    ) -> bool:
        """Send document via Telegram API."""
        try:
            session = await self._get_session()
            
            data = aiohttp.FormData()
            data.add_field("chat_id", chat_id)
            data.add_field(
                "document",
                content.encode(),
                filename=filename,
                content_type="text/plain"
            )
            
            async with session.post(
                f"{self.api_url}/sendDocument",
                data=data
            ) as response:
                return response.status == 200
                
        except Exception as e:
            logger.error(f"Failed to send document: {e}")
            return False
    
    async def close(self) -> None:
        """Close session."""
        if self._session and not self._session.closed:
            await self._session.close()
    
    # Synchronous wrappers for convenience
    def send_alert_sync(
        self,
        message: str,
        severity: str = "info",
        chat_id: Optional[str] = None,
        **kwargs
    ) -> bool:
        """Synchronous wrapper for send_alert."""
        return asyncio.run(self.send_alert(message, severity, chat_id, **kwargs))
    
    def send_status_update_sync(
        self,
        summary: Dict,
        chat_id: Optional[str] = None
    ) -> bool:
        """Synchronous wrapper for send_status_update."""
        return asyncio.run(self.send_status_update(summary, chat_id))


class TelegramGroupNotifier:
    """
    Manages notifications to multiple Telegram groups.
    """
    
    def __init__(self):
        self.bots: Dict[str, TelegramBotSender] = {}
        self.group_mappings: Dict[str, List[str]] = {}  # group -> chat_ids
    
    def add_bot(self, name: str, bot_token: str, default_chat_id: str) -> None:
        """Add a bot configuration."""
        self.bots[name] = TelegramBotSender(bot_token, default_chat_id)
    
    def map_group_to_chats(self, group: str, chat_ids: List[str]) -> None:
        """Map contact group to Telegram chat IDs."""
        self.group_mappings[group] = chat_ids
    
    async def notify_group(
        self,
        group: str,
        message: str,
        severity: str = "info",
        **kwargs
    ) -> Dict[str, bool]:
        """
        Send notification to all chats in group.
        
        Returns:
            Dict mapping chat_id to success status
        """
        chat_ids = self.group_mappings.get(group, [])
        results = {}
        
        for chat_id in chat_ids:
            # Use first available bot
            for bot in self.bots.values():
                success = await bot.send_alert(message, severity, chat_id, **kwargs)
                results[chat_id] = success
                break
        
        return results
