from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import SystemSetting

SESSION_LIFETIME_KEY = "auth.session_minutes"
DEFAULT_SESSION_MINUTES = 480
SESSION_DESCRIPTION = "Session lifetime in minutes (1–10080). Changes apply to newly issued sessions."


def validate_session_minutes(value) -> int:
    if type(value) is not int or not 1 <= value <= 10080:
        raise ValueError("Session lifetime must be an integer between 1 and 10080 minutes")
    return value


def session_minutes(db: Session) -> int:
    setting = db.scalar(select(SystemSetting).where(SystemSetting.key == SESSION_LIFETIME_KEY))
    if setting is None:
        return DEFAULT_SESSION_MINUTES
    return validate_session_minutes(setting.value_)
