"""
Telegram notification service for Best Wines Sweden
Sends notifications when wine lists are updated
"""

import os
import logging
import asyncio
from typing import Optional, List, Dict, Any
import json
from datetime import datetime
import httpx

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Service for sending Telegram notifications about wine list updates"""
    
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = os.getenv("WINE_BASE_URL", "https://wines.tokyo3.eu")
        
        if not self.bot_token:
            logger.warning("TELEGRAM_BOT_TOKEN not found. Telegram notifications disabled.")
            return
            
        if not self.chat_id:
            logger.warning("TELEGRAM_CHAT_ID not found. Telegram notifications disabled.")
            return
            
        # Construct Telegram API URL
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        logger.info("Telegram notifier initialized successfully")
    
    def is_enabled(self) -> bool:
        """Check if Telegram notifications are properly configured"""
        return (
            self.bot_token and 
            self.chat_id and
            hasattr(self, 'api_url')
        )
    
    async def send_list_update_notification(
        self, 
        toplist_name: str, 
        wines_count: int, 
        matches_count: int,
        new_wines: int = 0,
        updated_wines: int = 0,
        sync_duration: Optional[float] = None
    ) -> bool:
        """
        Send notification about wine list update
        
        Args:
            toplist_name: Name of the updated toplist
            wines_count: Total number of wines processed
            matches_count: Number of matches found with Systembolaget
            new_wines: Number of new wines added
            updated_wines: Number of existing wines updated
            sync_duration: Time taken for sync in seconds
            
        Returns:
            bool: True if notification sent successfully, False otherwise
        """
        if not self.is_enabled():
            logger.debug("Telegram notifications not enabled, skipping notification")
            return False
            
        try:
            # Create notification message
            message = self._format_update_message(
                toplist_name=toplist_name,
                wines_count=wines_count,
                matches_count=matches_count,
                new_wines=new_wines,
                updated_wines=updated_wines,
                sync_duration=sync_duration
            )
            
            # Send message via HTTP API
            success = await self._send_telegram_message(message)
            
            if success:
                logger.info(f"Successfully sent Telegram notification for '{toplist_name}'")
                return True
            else:
                return False
            
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram notification: {e}")
            return False
    
    def _format_update_message(
        self,
        toplist_name: str,
        wines_count: int,
        matches_count: int,
        new_wines: int = 0,
        updated_wines: int = 0,
        sync_duration: Optional[float] = None
    ) -> str:
        """Format the update notification message"""
        
        # Header with wine emoji
        message = f"🍷 <b>Wine List Updated</b>\n\n"
        
        # List name
        message += f"📋 <b>List:</b> {toplist_name}\n"
        
        # Stats
        message += f"🔢 <b>Wines Processed:</b> {wines_count}\n"
        message += f"🎯 <b>Matches Found:</b> {matches_count}\n"
        
        if new_wines > 0:
            message += f"✨ <b>New Wines:</b> {new_wines}\n"
        
        if updated_wines > 0:
            message += f"🔄 <b>Updated Wines:</b> {updated_wines}\n"
        
        # Match percentage
        if wines_count > 0:
            match_percentage = (matches_count / wines_count) * 100
            message += f"📊 <b>Match Rate:</b> {match_percentage:.1f}%\n"
        
        # Duration if provided
        if sync_duration:
            message += f"⏱️ <b>Duration:</b> {sync_duration:.1f}s\n"
        
        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        message += f"📅 <b>Updated:</b> {timestamp}\n"
        
        # Link to wine list
        message += f"\n🔗 <a href=\"{self.base_url}\">View Wine List</a>"
        
        return message
    
    async def _send_telegram_message(self, message: str) -> bool:
        """Send a message to Telegram using HTTP API"""
        try:
            async with httpx.AsyncClient() as client:
                payload = {
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML"
                }
                
                response = await client.post(self.api_url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                if result.get("ok"):
                    return True
                else:
                    logger.error(f"Telegram API error: {result.get('description', 'Unknown error')}")
                    return False
                    
        except httpx.HTTPError as e:
            logger.error(f"HTTP error sending Telegram message: {e}")
            return False
        except Exception as e:
            logger.error(f"Error sending Telegram message: {e}")
            return False
    
    async def send_error_notification(self, error_message: str, toplist_name: Optional[str] = None) -> bool:
        """Send notification about sync errors"""
        if not self.is_enabled():
            return False
            
        try:
            message = f"❌ <b>Wine Sync Error</b>\n\n"
            
            if toplist_name:
                message += f"📋 <b>List:</b> {toplist_name}\n"
            
            message += f"🚨 <b>Error:</b> {error_message}\n"
            
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            message += f"📅 <b>Time:</b> {timestamp}"
            
            success = await self._send_telegram_message(message)
            
            if success:
                logger.info("Successfully sent Telegram error notification")
                return True
            else:
                return False
            
        except Exception as e:
            logger.error(f"Failed to send Telegram error notification: {e}")
            return False
    
    async def send_test_notification(self) -> bool:
        """Send a test notification to verify configuration"""
        if not self.is_enabled():
            logger.warning("Cannot send test notification - Telegram not properly configured")
            return False
            
        try:
            message = (
                "🧪 <b>Test Notification</b>\n\n"
                "✅ Telegram notifications are working correctly!\n"
                f"📅 <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            success = await self._send_telegram_message(message)
            
            if success:
                logger.info("Successfully sent Telegram test notification")
                return True
            else:
                return False
            
        except Exception as e:
            logger.error(f"Failed to send Telegram test notification: {e}")
            return False


# Global notifier instance
telegram_notifier = TelegramNotifier()


async def notify_list_update(
    toplist_name: str, 
    wines_count: int, 
    matches_count: int,
    **kwargs
) -> bool:
    """Convenience function to send list update notification"""
    return await telegram_notifier.send_list_update_notification(
        toplist_name=toplist_name,
        wines_count=wines_count,
        matches_count=matches_count,
        **kwargs
    )


async def notify_error(error_message: str, toplist_name: Optional[str] = None) -> bool:
    """Convenience function to send error notification"""
    return await telegram_notifier.send_error_notification(
        error_message=error_message,
        toplist_name=toplist_name
    )


async def send_test_notification() -> bool:
    """Convenience function to send test notification"""
    return await telegram_notifier.send_test_notification()