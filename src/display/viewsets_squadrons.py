"""
REST API of squadrons (see display/services/squadrons.py for the rules): the squadrons a user is in, their members and
invitations, the invitations addressed to the user, and sharing a contest with a squadron.
"""

from django.http import Http404
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, permissions, serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from display.models import Contest, Squadron, SquadronContestShare, SquadronInvitation, SquadronMembership
from display.services import squadrons
from display.services.people_search import user_identities


class SquadronSerialiser(serializers.ModelSerializer):
    my_role = serializers.SerializerMethodField()
    member_count = serializers.SerializerMethodField()
    contest_count = serializers.SerializerMethodField()

    class Meta:
        model = Squadron
        fields = ("id", "name", "description", "created_at", "my_role", "member_count", "contest_count")
        read_only_fields = ("id", "created_at", "my_role", "member_count", "contest_count")

    def get_contest_count(self, squadron) -> int:
        return squadron.contests.count()

    def get_my_role(self, squadron) -> str | None:
        membership = squadrons.membership_of(squadron, self.context["request"].user)
        return membership.role if membership else None

    def get_member_count(self, squadron) -> int:
        return squadron.memberships.count()


class SquadronMemberSerialiser(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    user_id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    email_hint = serializers.CharField(read_only=True)
    role = serializers.CharField()
    joined_at = serializers.DateTimeField(read_only=True)


class SquadronInvitationSerialiser(serializers.ModelSerializer):
    squadron_name = serializers.CharField(source="squadron.name", read_only=True)
    squadron_description = serializers.CharField(source="squadron.description", read_only=True)
    invited_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SquadronInvitation
        fields = (
            "id",
            "squadron",
            "squadron_name",
            "squadron_description",
            "role",
            "status",
            "invited_by_name",
            "created_at",
        )
        read_only_fields = fields

    def get_invited_by_name(self, invitation) -> str:
        user = invitation.invited_by
        return f"{user.first_name} {user.last_name}".strip() if user else ""


class AdminSquadronInvitationSerialiser(SquadronInvitationSerialiser):
    """What an admin sees of the invitations they have sent: the address is masked, as in the contest permissions."""

    email_hint = serializers.SerializerMethodField()

    class Meta(SquadronInvitationSerialiser.Meta):
        fields = SquadronInvitationSerialiser.Meta.fields + ("email_hint",)
        read_only_fields = fields

    def get_email_hint(self, invitation) -> str:
        from display.services.people_search import mask_email_heavily

        return mask_email_heavily(invitation.email)


class SquadronDetailSerialiser(SquadronSerialiser):
    members = serializers.SerializerMethodField()
    invitations = serializers.SerializerMethodField()
    contests = serializers.SerializerMethodField()

    class Meta(SquadronSerialiser.Meta):
        fields = SquadronSerialiser.Meta.fields + ("members", "invitations", "contests")
        read_only_fields = fields

    def get_members(self, squadron) -> list:
        memberships = list(squadron.memberships.select_related("user"))
        identities = user_identities(membership.user for membership in memberships)
        return SquadronMemberSerialiser(
            [
                {
                    "id": membership.pk,
                    "user_id": membership.user_id,
                    **identities[membership.user_id],
                    "role": membership.role,
                    "joined_at": membership.joined_at,
                }
                for membership in memberships
            ],
            many=True,
        ).data

    def get_invitations(self, squadron) -> list:
        # Only an admin sees who has been invited
        if not squadrons.is_admin(squadron, self.context["request"].user):
            return []
        pending = squadron.invitations.filter(status=SquadronInvitation.PENDING).select_related(
            "invited_by", "squadron"
        )
        return AdminSquadronInvitationSerialiser(pending, many=True).data

    def get_contests(self, squadron) -> list:
        user = self.context["request"].user
        shares = squadron.squadroncontestshare_set.select_related("contest", "shared_by").order_by(
            "-contest__start_time"
        )
        return [share_payload(share, user) for share in shares]


def share_payload(share: SquadronContestShare, user) -> dict:
    """A contest shared with a squadron: who shared it, and whether [user] may stop that."""
    shared_by = share.shared_by
    return {
        "id": share.contest_id,
        "name": share.contest.name,
        "start_time": share.contest.start_time,
        "shared_by_name": f"{shared_by.first_name} {shared_by.last_name}".strip() if shared_by else "",
        "shared_by_me": shared_by is not None and shared_by.pk == user.pk,
        "can_remove": squadrons.can_stop_sharing(share, user),
    }


class InviteSerialiser(serializers.Serializer):
    identifier = serializers.CharField(help_text="A user id, as the people search gives, or an e-mail address.")
    role = serializers.ChoiceField(choices=SquadronMembership.ROLES, default=SquadronMembership.MEMBER)


class RoleSerialiser(serializers.Serializer):
    role = serializers.ChoiceField(choices=SquadronMembership.ROLES)


class ShareWithSquadronSerialiser(serializers.Serializer):
    squadron = serializers.IntegerField()


class ShareContestSerialiser(serializers.Serializer):
    contest = serializers.IntegerField()


class SquadronViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
    GenericViewSet,
):
    """The squadrons the user is a member of. Others do not exist as far as the user can tell."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SquadronSerialiser
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def get_queryset(self):
        return Squadron.objects.filter(memberships__user=self.request.user)

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SquadronDetailSerialiser
        if self.action == "invite":
            return InviteSerialiser
        if self.action == "member":
            return RoleSerialiser
        if self.action == "contests":
            return ShareContestSerialiser
        return SquadronSerialiser

    def create(self, request, *args, **kwargs):
        serialiser = self.get_serializer(data=request.data)
        serialiser.is_valid(raise_exception=True)
        squadron = squadrons.create_squadron(
            request.user,
            serialiser.validated_data["name"],
            serialiser.validated_data.get("description", ""),
        )
        return Response(SquadronSerialiser(squadron, context={"request": request}).data, status=status.HTTP_201_CREATED)

    def perform_update(self, serializer):
        squadrons.require_admin(serializer.instance, self.request.user)
        serializer.save()

    def perform_destroy(self, instance):
        squadrons.delete_squadron(instance, self.request.user)

    @extend_schema(request=InviteSerialiser, responses=SquadronInvitationSerialiser)
    @action(detail=True, methods=["post"])
    def invite(self, request, *args, **kwargs):
        squadron = self.get_object()
        serialiser = self.get_serializer(data=request.data)
        serialiser.is_valid(raise_exception=True)
        invitation = squadrons.invite(
            squadron, request.user, serialiser.validated_data["identifier"], serialiser.validated_data["role"]
        )
        return Response(AdminSquadronInvitationSerialiser(invitation).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["delete"], url_path=r"invitations/(?P<invitation_pk>\d+)")
    def invitation(self, request, invitation_pk=None, *args, **kwargs):
        squadron = self.get_object()
        invitation = get_object_or_404(SquadronInvitation, pk=invitation_pk, squadron=squadron)
        squadrons.revoke_invitation(invitation, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=RoleSerialiser, responses={200: RoleSerialiser, 204: None})
    @action(detail=True, methods=["put", "delete"], url_path=r"members/(?P<membership_pk>\d+)")
    def member(self, request, membership_pk=None, *args, **kwargs):
        squadron = self.get_object()
        membership = get_object_or_404(SquadronMembership, pk=membership_pk, squadron=squadron)
        if request.method == "DELETE":
            squadrons.remove_member(squadron, request.user, membership)
            return Response(status=status.HTTP_204_NO_CONTENT)
        serialiser = self.get_serializer(data=request.data)
        serialiser.is_valid(raise_exception=True)
        squadrons.change_role(squadron, request.user, membership, serialiser.validated_data["role"])
        return Response(serialiser.data)

    @extend_schema(request=None, responses={200: None})
    @action(detail=False, methods=["get"], url_path="contest-access")
    def contest_access(self, request, *args, **kwargs):
        """The contests the user can open through their squadrons, each with all the squadrons that give the access."""
        return Response(squadrons.contest_access_through_squadrons(request.user))

    @extend_schema(request=None, responses={200: None})
    @action(detail=True, methods=["get"], url_path="shareable-contests")
    def shareable_contests(self, request, *args, **kwargs):
        """The contests the user manages that can still be added to the squadron."""
        squadron = self.get_object()
        contests = squadrons.shareable_contests(squadron, request.user)[:200]
        return Response(
            [{"id": contest.pk, "name": contest.name, "start_time": contest.start_time} for contest in contests]
        )

    @extend_schema(request=ShareContestSerialiser, responses={201: None})
    @action(detail=True, methods=["post"])
    def contests(self, request, *args, **kwargs):
        """Give the squadron's members access to a contest the user manages."""
        squadron = self.get_object()
        serialiser = self.get_serializer(data=request.data)
        serialiser.is_valid(raise_exception=True)
        contest = get_object_or_404(Contest, pk=serialiser.validated_data["contest"])
        # A contest the user cannot manage is none of their business: say it does not exist
        if not request.user.has_perm("display.change_contest", contest):
            raise Http404
        share = squadrons.share_contest(contest, squadron, request.user)
        return Response(share_payload(share, request.user), status=status.HTTP_201_CREATED)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["delete"], url_path=r"contests/(?P<contest_pk>\d+)")
    def contest(self, request, contest_pk=None, *args, **kwargs):
        squadron = self.get_object()
        share = get_object_or_404(SquadronContestShare, squadron=squadron, contest_id=contest_pk)
        squadrons.unshare_contest(share.contest, squadron, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"])
    def leave(self, request, *args, **kwargs):
        squadron = self.get_object()
        squadrons.remove_member(squadron, request.user, squadrons.membership_of(squadron, request.user))
        return Response(status=status.HTTP_204_NO_CONTENT)


class SquadronInvitationViewSet(mixins.ListModelMixin, GenericViewSet):
    """The invitations addressed to the user that are waiting for an answer."""

    permission_classes = [permissions.IsAuthenticated]
    serializer_class = SquadronInvitationSerialiser
    pagination_class = None

    def get_queryset(self):
        return squadrons.pending_invitations_for(self.request.user)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"])
    def accept(self, request, *args, **kwargs):
        squadrons.accept_invitation(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(request=None, responses={204: None})
    @action(detail=True, methods=["post"])
    def decline(self, request, *args, **kwargs):
        squadrons.decline_invitation(self.get_object(), request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


def contest_squadrons_payload(contest: Contest, user) -> list:
    shares = contest.squadroncontestshare_set.select_related("squadron", "shared_by").order_by("squadron__name")
    payload = []
    for share in shares:
        shared_by = share.shared_by
        payload.append(
            {
                "id": share.squadron_id,
                "name": share.squadron.name,
                "shared_by_name": f"{shared_by.first_name} {shared_by.last_name}".strip() if shared_by else "",
                "can_remove": squadrons.can_stop_sharing(share, user),
            }
        )
    return payload


class ContestSquadronsMixin:
    """
    The squadrons a contest is shared with, added to ContestViewSet: GET lists them, POST {squadron} shares the contest
    with one of the user's squadrons and DELETE squadrons/<id>/ stops sharing.
    """

    @extend_schema(request=ShareWithSquadronSerialiser, responses={200: None})
    @action(
        detail=True,
        methods=["get", "post"],
        url_path="squadrons",
        permission_classes=[permissions.IsAuthenticated],
    )
    def shared_squadrons(self, request, *args, **kwargs):
        contest = self.get_object()
        if request.method == "POST":
            serialiser = ShareWithSquadronSerialiser(data=request.data)
            serialiser.is_valid(raise_exception=True)
            squadron = get_object_or_404(
                Squadron.objects.filter(memberships__user=request.user), pk=serialiser.validated_data["squadron"]
            )
            squadrons.share_contest(contest, squadron, request.user)
        elif not request.user.has_perm("display.change_contest", contest):
            return Response(status=status.HTTP_403_FORBIDDEN)
        return Response(contest_squadrons_payload(contest, request.user))

    @extend_schema(request=None, responses={200: None})
    @action(
        detail=True,
        methods=["delete"],
        url_path=r"squadrons/(?P<squadron_pk>\d+)",
        permission_classes=[permissions.IsAuthenticated],
    )
    def unshare_squadron(self, request, squadron_pk=None, *args, **kwargs):
        contest = self.get_object()
        squadron = get_object_or_404(Squadron, pk=squadron_pk, contests=contest)
        squadrons.unshare_contest(contest, squadron, request.user)
        return Response(contest_squadrons_payload(contest, request.user))
