from aiogram import Bot
from app.bot.keyboards import get_candidate_actions_keyboard
from app.scoring.schemas import FinalRecommendation
from app.bot.permissions import BotPermissions

class BotNotificationManager:
    """
    Handles formatting and sending notifications to HR.
    """
    
    def __init__(self, bot: Bot):
        self.bot = bot
        self.permissions = BotPermissions()

    async def notify_new_candidate(self, recommendation: FinalRecommendation):
        """
        Sends a rich HTML notification to all authorized HR IDs.
        """
        hr_ids = self.permissions.get_hr_ids()
        if not hr_ids:
            print("ERROR: No HR IDs configured. Notification not sent.")
            return

        message_html = self._format_hr_report(recommendation)
        
        keyboard = get_candidate_actions_keyboard(
            session_id=recommendation.session_id,
            candidate_name=recommendation.candidate_name
        )

        for hr_id in hr_ids:
            try:
                await self.bot.send_message(
                    chat_id=hr_id,
                    text=message_html,
                    parse_mode="HTML",
                    reply_markup=keyboard
                )
            except Exception as e:
                print(f"Failed to send notification to HR {hr_id}: {e}")

    def _format_hr_report(self, rec: FinalRecommendation) -> str:
        """Formats the bilingual HTML report for Telegram with RU/UZ separation."""
        
        # Color Indicators (emojis)
        score_emoji = "🟢" if rec.final_score >= 70 else "🟡" if rec.final_score >= 50 else "🔴"
        integrity_emoji = "✅" if rec.score_breakdown.honesty_score >= 70 else "⚠️" if rec.score_breakdown.honesty_score >= 50 else "❌"
        confidence_emoji = "🎯" if rec.confidence == "high" else "⚖️" if rec.confidence == "medium" else "❓"

        # Russian block
        ru_header = f"🇷🇺 <b>НОВЫЙ КАНДИДАТ</b>\n"
        ru_details = (
            f"👤 <b>Кандидат:</b> {rec.candidate_name}\n"
            f"🆔 <b>Сессия:</b> <code>{rec.session_id}</code>\n"
            f"───────────────────\n"
            f"{score_emoji} <b>AI Балл:</b> {rec.final_score}/100\n"
            f"{integrity_emoji} <b>Честность:</b> {rec.score_breakdown.honesty_score}%\n"
            f"{confidence_emoji} <b>Уверенность:</b> {rec.confidence.upper()}\n"
            f"───────────────────\n"
            f"<b>📊 Решение:</b> <i>{rec.decision}</i>\n"
            f"<b>💬 Комментарий:</b> {rec.hr_comment}\n"
        )

        # Uzbek block
        uz_header = f"🇺🇿 <b>YANGI NOMZOD</b>\n"
        uz_details = (
            f"👤 <b>Nomzod:</b> {rec.candidate_name}\n"
            f"{score_emoji} <b>AI Ball:</b> {rec.final_score}/100\n"
            f"{integrity_emoji} <b>Rostgo'ylik:</b> {rec.score_breakdown.honesty_score}%\n"
            f"{confidence_emoji} <b>Ishonch:</b> {rec.confidence.upper()}\n"
            f"───────────────────\n"
            f"<b>📊 Bashorat:</b> <i>{rec.decision}</i>\n"
            f"<b>💬 Izoh:</b> {rec.hr_comment}\n"
        )

        reasons_text = f"<b>🚨 Reasons / Sabablar:</b>\n" + "\n".join([f"• {f}" for f in rec.flags[:3]])

        return (
            f"{ru_header}\n{ru_details}\n"
            f"<b>---------------------</b>\n\n"
            f"{uz_header}\n{uz_details}\n"
            f"───────────────────\n"
            f"{reasons_text}"
        )
