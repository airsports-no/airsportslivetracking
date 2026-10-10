"""Who tracks with the mobile apps without a store subscription ("free access")."""

from dataclasses import dataclass
import datetime
from typing import Optional

from display.models import UserEntitlementGrant

SOURCE_STAFF = "staff"
SOURCE_GRANT = "grant"


@dataclass(frozen=True)
class FreeTrackingAccess:
    source: str
    expires_at: Optional[datetime.datetime] = None

    def as_dict(self) -> dict:
        return {"source": self.source, "expires_at": self.expires_at}


def free_tracking_access(user) -> Optional[FreeTrackingAccess]:
    """
    Staff and superusers always have it; anybody else needs an active ``app_tracking`` UserEntitlementGrant (Django admin:
    with optional expiry, notes and who granted it). Subscriptions bought in the stores are not known here: the apps ask
    the store, and this is only the operator's way to give someone tracking for free.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return None
    if user.is_staff or user.is_superuser:
        return FreeTrackingAccess(SOURCE_STAFF)
    grants = UserEntitlementGrant.objects.filter(user=user, kind=UserEntitlementGrant.KIND_APP_TRACKING, is_active=True)
    active = [g for g in grants if g.is_active_now]
    if not active:
        return None
    # The grant that lasts longest wins; one without expiry lasts forever.
    best = max(active, key=lambda g: datetime.datetime.max.replace(tzinfo=datetime.timezone.utc) if g.expires_at is None else g.expires_at)
    return FreeTrackingAccess(SOURCE_GRANT, best.expires_at)
