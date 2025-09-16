#!/usr/bin/env python3
"""
Telegram Notification Utilities for XAU Signal Tools

This module provides functions to send trading signals and notifications
to Telegram using the Bot API without external libraries.
"""

import json
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime
from logger import setup_logger
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from utils import format_dual_timezone, convert_to_utc3, get_utc3_now

logger = setup_logger()

class TelegramNotifier:
    def __init__(self, bot_token=None, chat_id=None):
        """
        Initialize Telegram notifier
        
        Args:
            bot_token: str - Telegram bot token (optional, uses config if not provided)
            chat_id: str - Telegram chat ID (optional, uses config if not provided)
        """
        self.bot_token = bot_token or TELEGRAM_BOT_TOKEN
        self.chat_id = chat_id or TELEGRAM_CHAT_ID
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"
        
        if not self.bot_token or not self.chat_id:
            logger.warning("Telegram bot token or chat ID not configured. Notifications will be disabled.")
            self.enabled = False
        else:
            self.enabled = True
            logger.info("Telegram notifier initialized")
    
    def send_message(self, message, parse_mode="HTML", disable_web_page_preview=True):
        """
        Send a message to Telegram
        
        Args:
            message: str - Message to send
            parse_mode: str - Message formatting (HTML, Markdown, or None)
            disable_web_page_preview: bool - Disable link previews
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.enabled:
            logger.debug("Telegram notifications disabled - message not sent")
            return False
            
        try:
            # Prepare the data
            data = {
                'chat_id': self.chat_id,
                'text': message,
                'parse_mode': parse_mode,
                'disable_web_page_preview': disable_web_page_preview
            }
            
            # Encode data
            data_encoded = urllib.parse.urlencode(data).encode('utf-8')
            
            # Create request
            url = f"{self.base_url}/sendMessage"
            request = urllib.request.Request(url, data=data_encoded, method='POST')
            request.add_header('Content-Type', 'application/x-www-form-urlencoded')
            
            # Send request
            with urllib.request.urlopen(request, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                
                if result.get('ok'):
                    logger.debug("Telegram message sent successfully")
                    return True
                else:
                    logger.error(f"Telegram API error: {result.get('description', 'Unknown error')}")
                    return False
                    
        except urllib.error.URLError as e:
            logger.error(f"Network error sending Telegram message: {e}")
            return False
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error in Telegram response: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error sending Telegram message: {e}")
            return False
    
    def send_signal_notification(self, signal_data):
        """
        Send trading signal notification to Telegram
        
        Args:
            signal_data: dict - Signal information from signal detector
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not signal_data:
            return False
            
        try:
            # Extract signal information
            signal_type = signal_data.get('signal_type', 'UNKNOWN')
            condition = signal_data.get('condition', 'UNKNOWN')
            entry_price = signal_data.get('entry_price', 0)
            timestamp = signal_data.get('timestamp', get_utc3_now())
            confidence = signal_data.get('confidence', 'N/A')
            
            # Format timestamp with dual timezone
            if isinstance(timestamp, str):
                try:
                    # Try to parse and format with timezone info
                    dt = datetime.strptime(timestamp, '%Y-%m-%d %H:%M:%S')
                    time_str = format_dual_timezone(convert_to_utc3(dt))
                except:
                    time_str = timestamp  # Fallback to original string
            else:
                time_str = format_dual_timezone(convert_to_utc3(timestamp))
            
            # Create signal message
            emoji = "🟢" if signal_type == "LONG" else "🔴"
            direction_emoji = "📈" if signal_type == "LONG" else "📉"
            display_direction = "BUY" if signal_type == "LONG" else "SELL"
            
            message = f"""
{emoji} <b>XAU/USD Trading Signal</b> {direction_emoji}

🎯 <b>Direction:</b> {display_direction}
📊 <b>Pattern:</b> {condition}
💰 <b>Entry Price:</b> ${entry_price:.2f}
📈 <b>Confidence:</b> {confidence}%
🕐 <b>Time:</b> {time_str}
            """.strip()
            
            return self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error formatting signal notification: {e}")
            return False
    
    def send_backtest_summary(self, results_summary):
        """
        Send backtest results summary to Telegram
        
        Args:
            results_summary: dict - Backtest results summary
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not results_summary:
            return False
            
        try:
            from config import TP_AMOUNT, SL_AMOUNT, BACKTEST_START_DATE, BACKTEST_END_DATE
            
            total_trades = results_summary.get('total_trades', 0)
            wins = results_summary.get('wins', 0)
            losses = results_summary.get('losses', 0)
            win_rate = results_summary.get('win_rate', 0)
            total_pnl = results_summary.get('total_pnl', 0)
            total_pnl_percentage = results_summary.get('total_pnl_percentage', 0)
            avg_win = results_summary.get('avg_win', 0)
            avg_loss = results_summary.get('avg_loss', 0)
            
            # Create backtest summary message
            message_parts = [
                "📊 <b>XAU/USD Backtest Summary</b>",
                "",
                f"🕐 <b>Backtest Time:</b> From {BACKTEST_START_DATE} To {BACKTEST_END_DATE}",
                f"⚖️ <b>TP/SL:</b> {TP_AMOUNT}/{SL_AMOUNT}",
                ""
            ]
            
            message_parts.extend([
                "📈 <b>Performance Overview:</b>",
                f"• Total Trades: {total_trades}",
                f"• Wins: {wins} | Losses: {losses}",
                f"• Win Rate: {win_rate:.2f}%",
                "",
                "💰 <b>P&L Analysis:</b>",
                f"• Total PnL: ${total_pnl:.4f}",
                f"• Total PnL%: {total_pnl_percentage:.4f}%",
                f"• Avg Win: ${avg_win:.4f}",
                f"• Avg Loss: ${avg_loss:.4f}"
            ])
            
            message = "\n".join(message_parts)
            
            return self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error formatting backtest summary: {e}")
            return False
    
    def send_trade_notification(self, trade_data):
        """
        Send individual trade result notification
        
        Args:
            trade_data: dict - Trade result data
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not trade_data:
            return False
            
        try:
            signal_type = trade_data.get('signal_type', 'UNKNOWN')
            result = trade_data.get('result', 'UNKNOWN')
            entry_price = trade_data.get('entry_price', 0)
            exit_price = trade_data.get('exit_price', 0)
            pnl = trade_data.get('pnl', 0)
            hit_type = trade_data.get('hit_type', 'UNKNOWN')
            duration_minutes = trade_data.get('duration_minutes', 0)
            entry_time = trade_data.get('entry_time', get_utc3_now())
            exit_time = trade_data.get('exit_time', get_utc3_now())
            
            # Format timestamps
            entry_str = entry_time.strftime('%H:%M:%S') if hasattr(entry_time, 'strftime') else str(entry_time)
            exit_str = exit_time.strftime('%H:%M:%S') if hasattr(exit_time, 'strftime') else str(exit_time)
            
            # Choose emojis based on result
            if result == 'WIN':
                result_emoji = "✅"
                color_emoji = "🟢"
            else:
                result_emoji = "❌"
                color_emoji = "🔴"
            
            direction_emoji = "📈" if signal_type == "LONG" else "📉"
            display_direction = "BUY" if signal_type == "LONG" else "SELL"
            
            message = f"""
{result_emoji} <b>Trade Closed</b> {color_emoji}

{direction_emoji} <b>{display_direction}</b> | <b>{result}</b>
💰 <b>PnL:</b> ${pnl:.4f}

📊 <b>Trade Details:</b>
• Entry: ${entry_price:.2f} at {entry_str}
• Exit: ${exit_price:.2f} at {exit_str}
• Hit: {hit_type}
• Duration: {duration_minutes} minutes

<i>XAU Signal Tools</i>
            """.strip()
            
            return self.send_message(message)
            
        except Exception as e:
            logger.error(f"Error formatting trade notification: {e}")
            return False
    
    def send_system_notification(self, message, level="INFO"):
        """
        Send system notification (errors, warnings, info)
        
        Args:
            message: str - Notification message
            level: str - Log level (INFO, WARNING, ERROR)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Choose emoji based on level
            level_emojis = {
                "INFO": "ℹ️",
                "WARNING": "⚠️", 
                "ERROR": "🚨"
            }
            
            emoji = level_emojis.get(level.upper(), "ℹ️")
            timestamp = format_dual_timezone(get_utc3_now())
            
            formatted_message = f"""
{emoji} <b>System {level}</b>

{message}

🕐 <i>{timestamp}</i>
            """.strip()
            
            return self.send_message(formatted_message)
            
        except Exception as e:
            logger.error(f"Error sending system notification: {e}")
            return False
    
    def test_connection(self):
        """
        Test Telegram bot connection
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        test_message = f"""
🤖 <b>XAU Signal Tools</b>

✅ Telegram bot connection test successful!

🕐 <i>{format_dual_timezone(get_utc3_now())}</i>
        """.strip()
        
        success = self.send_message(test_message)
        
        if success:
            logger.info("Telegram connection test successful")
        else:
            logger.error("Telegram connection test failed")
            
        return success

# Global instance for easy import
telegram_notifier = TelegramNotifier()

def send_signal_notification(signal_data):
    """Convenience function to send signal notification"""
    return telegram_notifier.send_signal_notification(signal_data)

def send_trade_notification(trade_data):
    """Convenience function to send trade notification"""
    return telegram_notifier.send_trade_notification(trade_data)

def send_backtest_summary(results_summary):
    """Convenience function to send backtest summary"""
    return telegram_notifier.send_backtest_summary(results_summary)

def send_system_notification(message, level="INFO"):
    """Convenience function to send system notification"""
    return telegram_notifier.send_system_notification(message, level)

def test_telegram_connection():
    """Convenience function to test Telegram connection"""
    return telegram_notifier.test_connection()