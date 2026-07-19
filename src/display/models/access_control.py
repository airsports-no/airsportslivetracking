import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ClubManagerMembership(models.Model):
    OWNER = "owner"
    MANAGER = "manager"
    ROLES = ((OWNER, "Owner"), (MANAGER, "Manager"))

    club = models.ForeignKey("Club", on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLES, default=MANAGER)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("club", "user")

    def __str__(self):
        return f"{self.user} manages {self.club}"


class TokenType(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True, default="")
    contestant_limit = models.IntegerField()
    task_limit = models.IntegerField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class UserTokenGrant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token_type = models.ForeignKey(TokenType, on_delete=models.PROTECT)
    quantity_total = models.IntegerField()
    quantity_consumed = models.IntegerField(default=0)
    purchase_reference = models.CharField(max_length=200, blank=True, default="")
    notes = models.TextField(blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_token_grants",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_token_grants",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    @property
    def quantity_remaining(self) -> int:
        return max(self.quantity_total - self.quantity_consumed, 0)

    @property
    def has_available_tokens(self) -> bool:
        return self.quantity_remaining > 0

    def clean(self):
        super().clean()
        if self.quantity_total < 0:
            raise ValidationError("quantity_total cannot be negative")
        if self.quantity_consumed < 0:
            raise ValidationError("quantity_consumed cannot be negative")
        if self.quantity_consumed > self.quantity_total:
            raise ValidationError("quantity_consumed cannot exceed quantity_total")

    def __str__(self):
        return f"{self.user} · {self.token_type} ({self.quantity_remaining} remaining)"


class ContestTokenAssignment(models.Model):
    contest = models.OneToOneField("Contest", on_delete=models.CASCADE)
    token_grant = models.ForeignKey(UserTokenGrant, on_delete=models.PROTECT)
    token_type = models.ForeignKey(TokenType, on_delete=models.PROTECT)
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_contest_tokens",
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-assigned_at",)

    def clean(self):
        super().clean()
        if self.token_grant_id and self.token_type_id and self.token_grant.token_type_id != self.token_type_id:
            raise ValidationError("Contest token assignment must use the token type from the selected token grant")

    def __str__(self):
        return f"{self.contest} uses {self.token_type}"


class AccessGrant(models.Model):
    FREE = "free"
    SINGLE_EVENT = "single_event"
    ANNUAL_CLUB_PASS = "annual_club_pass"
    MANUAL_OVERRIDE = "manual_override"
    TOKEN = "token"
    TIERS = (
        (FREE, "Free"),
        (SINGLE_EVENT, "Single event"),
        (ANNUAL_CLUB_PASS, "Annual club pass"),
        (MANUAL_OVERRIDE, "Manual override"),
        (TOKEN, "Token"),
    )

    DRAFT = "draft"
    ACTIVE = "active"
    EXPIRED = "expired"
    CANCELLED = "cancelled"
    STATUSES = (
        (DRAFT, "Draft"),
        (ACTIVE, "Active"),
        (EXPIRED, "Expired"),
        (CANCELLED, "Cancelled"),
    )

    club = models.ForeignKey("Club", on_delete=models.CASCADE, null=True, blank=True)
    contest = models.ForeignKey("Contest", on_delete=models.CASCADE, null=True, blank=True)
    tier = models.CharField(max_length=40, choices=TIERS)
    status = models.CharField(max_length=20, choices=STATUSES, default=DRAFT)
    starts_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    contestant_limit = models.IntegerField(null=True, blank=True)
    task_limit = models.IntegerField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")
    invoice_reference = models.CharField(max_length=200, blank=True, default="")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_access_grants",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_access_grants",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)

    def clean(self):
        super().clean()
        if bool(self.club_id) == bool(self.contest_id):
            raise ValidationError("AccessGrant must target exactly one of club or contest")

    @property
    def is_active(self) -> bool:
        now = datetime.datetime.now(datetime.timezone.utc)
        if self.status != self.ACTIVE:
            return False
        if self.starts_at and self.starts_at > now:
            return False
        if self.expires_at and self.expires_at <= now:
            return False
        return True

    def __str__(self):
        target = self.club or self.contest
        return f"{self.get_tier_display()} for {target}"


class AccessResolution:
    def __init__(
        self,
        *,
        tier_code: str,
        tier_label: str,
        source_type: str,
        source_id: int | None,
        contestant_limit: int | None,
        task_limit: int | None,
        contestants_used: int,
        tasks_used: int,
        enforcement_mode: str,
        token_grant_id: int | None = None,
        token_type_id: int | None = None,
    ):
        self.tier_code = tier_code
        self.tier_label = tier_label
        self.source_type = source_type
        self.source_id = source_id
        self.contestant_limit = contestant_limit
        self.task_limit = task_limit
        self.contestants_used = contestants_used
        self.tasks_used = tasks_used
        self.enforcement_mode = enforcement_mode
        self.token_grant_id = token_grant_id
        self.token_type_id = token_type_id
