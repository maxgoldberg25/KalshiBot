"""
Alert notifications (Slack, email, etc.)
"""

from typing import Optional

import httpx
import structlog

from kalshi_bot.config import settings

logger = structlog.get_logger()


async def send_alert(
    message: str,
    level: str = "info",
    title: Optional[str] = None,
) -> bool:
    """
    Send an alert notification.
    
    Currently supports Slack webhooks.
    
    Args:
        message: Alert message
        level: Alert level (info, warning, error)
        title: Optional title for the alert
        
    Returns:
        True if sent successfully
    """
    # Skip if no webhook configured
    if not settings.slack_webhook_url:
        logger.debug("alert_skipped", reason="No Slack webhook configured")
        return False
    
    # Format message with emoji based on level
    emoji_map = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "🚨",
        "success": "✅",
    }
    emoji = emoji_map.get(level, "📢")
    
    formatted_title = title or f"Kalshi Bot Alert ({level.upper()})"
    
    # Slack message payload
    payload = {
        "text": f"{emoji} *{formatted_title}*\n{message}",
        "username": "Kalshi Bot",
        "icon_emoji": ":robot_face:",
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                settings.slack_webhook_url,
                json=payload,
                timeout=10.0,
            )
            
            if response.status_code == 200:
                logger.info(
                    "alert_sent",
                    level=level,
                    title=formatted_title,
                )
                return True
            else:
                logger.error(
                    "alert_failed",
                    status_code=response.status_code,
                    response=response.text,
                )
                return False
                
    except Exception as e:
        logger.error("alert_error", error=str(e))
        return False


async def send_daily_report_alert(report: str) -> bool:
    """Send daily report as Slack alert."""
    # Truncate if too long for Slack
    max_length = 3000
    if len(report) > max_length:
        report = report[:max_length] + "\n... (truncated)"
    
    return await send_alert(
        message=f"```\n{report}\n```",
        level="info",
        title="Daily Trading Report",
    )


async def send_error_alert(error: str, context: Optional[str] = None) -> bool:
    """Send error alert."""
    message = error
    if context:
        message = f"{context}\n\n{error}"
    
    return await send_alert(
        message=message,
        level="error",
        title="Trading Error",
    )


async def send_trade_alert(
    ticker: str,
    side: str,
    quantity: int,
    price: int,
    status: str,
) -> bool:
    """Send trade execution alert."""
    message = (
        f"*{ticker}*\n"
        f"Side: {side.upper()}\n"
        f"Quantity: {quantity} contracts\n"
        f"Price: {price}¢\n"
        f"Status: {status}"
    )
    
    level = "success" if status == "filled" else "info"
    
    return await send_alert(
        message=message,
        level=level,
        title="Trade Update",
    )
