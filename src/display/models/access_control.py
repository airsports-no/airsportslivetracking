import datetime

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class ClubManagerMembership(models.Model):
    OWNER = "owner"
    MANAGER = "manager"
    ROLES = ((OWNER, "Owner"), (MANAGER, "Manager"))

    club = models.ForeignKey("Club", on_delete=models.CASCADE, help_text="Club that grants organizer or billing-management rights.")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, help_text="Logged-in user who may manage contests and access for this club.")
    role = models.CharField(max_length=20, choices=ROLES, default=MANAGER, help_text="Whether this user is a general manager or the primary owner for the club.")
    is_active = models.BooleanField(default=True, help_text="If false, this membership is ignored when resolving club-based access rights.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_club_manager_memberships",
        help_text="Backend user who created this club manager membership.",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_club_manager_memberships",
        help_text="Backend user who last updated this club manager membership.",
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this club manager membership was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="When this club manager membership was last updated.")

    class Meta:
        unique_together = ("club", "user")

    def clean(self):
        super().clean()
        if self.role == self.OWNER and not self.is_active:
            active_owner_exists = ClubManagerMembership.objects.filter(
                club=self.club,
                role=self.OWNER,
                is_active=True,
            ).exclude(pk=self.pk).exists()
            if not active_owner_exists:
                raise ValidationError("A club must always retain at least one active owner membership")

    def __str__(self):
        return f"{self.user} manages {self.club}"


class TokenType(models.Model):
    name = models.CharField(max_length=200, unique=True, help_text="Human-friendly name for the token package, shown in admin and contest UI.")
    description = models.TextField(blank=True, default="", help_text="Explain how this token package should be used and what its limits mean.")
    contestant_limit = models.IntegerField(help_text="Maximum number of competing pilots that may start under a contest using this token package.")
    task_type_groups = models.JSONField(
        default=list,
        blank=True,
        help_text="Task-type groups this token package may be used for. Leave empty to keep the default free-tier task-group availability only.",
    )
    validity_days = models.IntegerField(null=True, blank=True, help_text="Number of days the token remains valid after activation. Leave empty for no automatic expiry.")
    is_active = models.BooleanField(default=True, help_text="Inactive token types stay in history but cannot be offered for new grants or assignments.")
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this token type was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="When this token type definition was last updated.")

    def __str__(self):
        return self.name


class UserTokenGrant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, help_text="User who owns and may consume this token grant.")
    token_type = models.ForeignKey(TokenType, on_delete=models.PROTECT, help_text="Token package that defines contestant and task limits for each use of this grant.")
    quantity_total = models.IntegerField(help_text="Total number of token uses purchased or manually granted to the user.")
    quantity_consumed = models.IntegerField(default=0, help_text="Number of token uses already consumed by contest assignments or replacements.")
    purchase_reference = models.CharField(max_length=200, blank=True, default="", help_text="Optional invoice, transfer, or operator reference for auditing how this grant was issued.")
    notes = models.TextField(blank=True, default="", help_text="Internal notes about the grant, customer, or manual adjustments.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_token_grants",
        help_text="Backend user who created this token grant record.",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_token_grants",
        help_text="Backend user who last updated this token grant record.",
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this token grant was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="When this token grant was last updated.")

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
    contest = models.OneToOneField("Contest", on_delete=models.CASCADE, help_text="Contest whose access limits are currently defined by the assigned token.")
    token_grant = models.ForeignKey(UserTokenGrant, on_delete=models.PROTECT, help_text="Specific user token grant that was consumed for this contest.")
    token_type = models.ForeignKey(TokenType, on_delete=models.PROTECT, help_text="Snapshot reference to the token type used by this contest assignment.")
    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_contest_tokens",
        help_text="Backend user who assigned or replaced the token for this contest.",
    )
    assigned_at = models.DateTimeField(auto_now_add=True, help_text="When this token was assigned to the contest.")
    activated_at = models.DateTimeField(null=True, blank=True, help_text="When the first billable guest start activated this token assignment.")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="When this contest token assignment expires and the contest enters archive mode.")

    class Meta:
        ordering = ("-assigned_at",)

    @property
    def is_active_now(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        return self.expires_at is None or self.expires_at > now

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

    club = models.ForeignKey("Club", on_delete=models.CASCADE, null=True, blank=True, help_text="Club that receives this pass or override. Leave blank if this grant applies to a single contest.")
    contest = models.ForeignKey("Contest", on_delete=models.CASCADE, null=True, blank=True, help_text="Contest that receives this single-event pass or manual override. Leave blank for club-level grants.")
    tier = models.CharField(max_length=40, choices=TIERS, help_text="Type of access entitlement, such as free tier, annual pass, single-event pass, manual override, or token-backed access.")
    status = models.CharField(max_length=20, choices=STATUSES, default=DRAFT, help_text="Operational state of the grant. Only active grants inside their time window are enforced.")
    starts_at = models.DateTimeField(null=True, blank=True, help_text="Optional start time from which the grant becomes valid.")
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Optional expiry time after which the grant no longer applies.")
    contestant_limit = models.IntegerField(null=True, blank=True, help_text="Competing pilot cap enforced by this grant. Leave empty for unlimited competing pilots.")
    task_type_groups = models.JSONField(
        default=list,
        blank=True,
        help_text="Task-type groups this access grant allows. Leave empty to keep the default free-tier task-group availability only.",
    )
    notes = models.TextField(blank=True, default="", help_text="Internal operator notes about the grant, agreement, or special handling.")
    invoice_reference = models.CharField(max_length=200, blank=True, default="", help_text="Optional accounting or payment reference for this grant.")
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_access_grants",
        help_text="Backend user who created this access grant record.",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="updated_access_grants",
        help_text="Backend user who last updated this access grant record.",
    )
    created_at = models.DateTimeField(auto_now_add=True, help_text="When this access grant was created.")
    updated_at = models.DateTimeField(auto_now=True, help_text="When this access grant was last updated.")

    class Meta:
        ordering = ("-created_at",)

    def derive_tier(self) -> str | None:
        if self.club_id:
            return self.ANNUAL_CLUB_PASS
        if self.contest_id:
            return self.SINGLE_EVENT
        return None

    def clean(self):
        super().clean()
        if bool(self.club_id) == bool(self.contest_id):
            raise ValidationError("AccessGrant must target exactly one of club or contest")
        derived_tier = self.derive_tier()
        if derived_tier is not None:
            self.tier = derived_tier

    def save(self, *args, **kwargs):
        derived_tier = self.derive_tier()
        if derived_tier is not None:
            self.tier = derived_tier
        super().save(*args, **kwargs)

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
        contestants_used: int,
        enforcement_mode: str,
        token_grant_id: int | None = None,
        token_type_id: int | None = None,
        package_contestant_limit: int | None = None,
        free_contestant_limit: int | None = None,
        contestant_limit_uses_free_default: bool = False,
        allowed_task_type_groups: list[str] | None = None,
        package_task_type_groups: list[str] | None = None,
        free_task_type_groups: list[str] | None = None,
    ):
        self.tier_code = tier_code
        self.tier_label = tier_label
        self.source_type = source_type
        self.source_id = source_id
        self.contestant_limit = contestant_limit
        self.contestants_used = contestants_used
        self.enforcement_mode = enforcement_mode
        self.token_grant_id = token_grant_id
        self.token_type_id = token_type_id
        self.package_contestant_limit = package_contestant_limit if package_contestant_limit is not None else contestant_limit
        self.free_contestant_limit = free_contestant_limit
        self.contestant_limit_uses_free_default = contestant_limit_uses_free_default
        self.allowed_task_type_groups = allowed_task_type_groups or []
        self.package_task_type_groups = package_task_type_groups or []
        self.free_task_type_groups = free_task_type_groups or []

    @property
    def uses_more_advantageous_free_limits(self):
        return self.contestant_limit_uses_free_default
