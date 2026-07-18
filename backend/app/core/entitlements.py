"""Plan entitlements — the single place that decides what Free vs Pro can do."""

from datetime import UTC, datetime

from app.models.user import User

# Free-tier caps. Pro is unlimited.
FREE_ALERT_LIMIT = 3
FREE_WATCHLIST_LIMIT = 25


def is_pro(user: User) -> bool:
    """True while the account holds an active Pro plan.

    A cancelled subscription keeps Pro until plan_expires_at passes.
    """
    if user.plan != "pro":
        return False
    expires = user.plan_expires_at
    if expires is not None and expires < datetime.now(UTC):
        return False
    return True
