from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from app.bot.schemas import HRAction

def get_candidate_actions_keyboard(session_id: str, candidate_name: str, cv_filename: str = None) -> InlineKeyboardMarkup:
    """
    Creates an inline keyboard for HR to take action on a candidate.
    """
    builder = InlineKeyboardBuilder()
    
    # Callback data format: action:session_id
    builder.row(
        InlineKeyboardButton(
            text="✅ Invite", 
            callback_data=f"{HRAction.INVITE.value}:{session_id}"
        ),
        InlineKeyboardButton(
            text="❌ Reject", 
            callback_data=f"{HRAction.REJECT.value}:{session_id}"
        )
    )
    
    # Second row: Review and CV
    row2 = [
        InlineKeyboardButton(
            text="⏳ Review", 
            callback_data=f"{HRAction.REVIEW.value}:{session_id}"
        )
    ]
    
    if cv_filename:
        # Assuming the base URL is known or passed. Since it's a web app, we can use a URL.
        # For now, let's use a placeholder URL that matches our mount
        row2.append(
            InlineKeyboardButton(
                text="📄 CV", 
                url=f"https://yourdomain.com/uploads/{cv_filename}" # Replace with actual domain
            )
        )
    
    builder.row(*row2)
    
    return builder.as_markup()
