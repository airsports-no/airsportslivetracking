from django.conf import settings
from django.db import models


class Squadron(models.Model):
    """
    A group of people who compete together. Contests are shared with a squadron (Contest.shared_with_squadrons) and every
    member of the squadron is then in the contest's audience: they can see it, including its private tasks, and take part
    in it. A squadron never gives the right to manage a contest, and its admins only manage who the members are.
    """

    name = models.CharField(
        max_length=100, help_text="Shown to the members and in the list of squadrons a contest can be shared with."
    )
    description = models.TextField(
        blank=True, default="", help_text="What the squadron is for, shown to the members and to the people invited."
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="created_squadrons"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    invite_token = models.CharField(
        max_length=64,
        unique=True,
        null=True,
        blank=True,
        help_text="Anybody logged in who opens the squadron's invite link with this token can join as a member. Empty: the link is off.",
    )

    class Meta:
        ordering = ("name",)

    def __str__(self):
        return self.name

    @property
    def admin_count(self) -> int:
        return self.memberships.filter(role=SquadronMembership.ADMIN).count()


class SquadronMembership(models.Model):
    ADMIN = "admin"
    MEMBER = "member"
    ROLES = ((ADMIN, "Admin"), (MEMBER, "Member"))

    squadron = models.ForeignKey(Squadron, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="squadron_memberships")
    role = models.CharField(max_length=10, choices=ROLES, default=MEMBER)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("joined_at",)
        constraints = [models.UniqueConstraint(fields=["squadron", "user"], name="unique_squadron_membership")]

    def __str__(self):
        return f"{self.user} in {self.squadron} ({self.role})"


class SquadronContestShare(models.Model):
    """
    A contest shared with a squadron (Contest.shared_with_squadrons), with who shared it: a member may stop sharing only
    what they shared themselves, an admin of the squadron anything.
    """

    squadron = models.ForeignKey(Squadron, on_delete=models.CASCADE)
    contest = models.ForeignKey("Contest", on_delete=models.CASCADE)
    shared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )
    shared_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-shared_at",)
        constraints = [models.UniqueConstraint(fields=["squadron", "contest"], name="unique_squadron_contest_share")]

    def __str__(self):
        return f"{self.contest} with {self.squadron}"


class SquadronInvitation(models.Model):
    """
    An invitation to join a squadron, addressed to an e-mail address so that it reaches an existing user and one who signs
    up later alike. Nobody joins without accepting, whatever role they are invited to.
    """

    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    REVOKED = "revoked"
    STATUSES = ((PENDING, "Pending"), (ACCEPTED, "Accepted"), (DECLINED, "Declined"), (REVOKED, "Revoked"))

    squadron = models.ForeignKey(Squadron, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField(help_text="Lower case. The invitation is shown to the user with this e-mail address.")
    role = models.CharField(max_length=10, choices=SquadronMembership.ROLES, default=SquadronMembership.MEMBER)
    status = models.CharField(max_length=10, choices=STATUSES, default=PENDING)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sent_squadron_invitations",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        # At most one pending invitation per squadron and e-mail is kept by the invitation service: MySQL has no
        # conditional unique constraints.

    def save(self, *args, **kwargs):
        self.email = self.email.strip().lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.email} to {self.squadron} ({self.status})"
