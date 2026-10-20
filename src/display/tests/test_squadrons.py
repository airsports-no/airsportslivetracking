"""
Squadrons: the members of a squadron a contest is shared with are in its audience; invitations, roles and sharing.
"""

import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from guardian.shortcuts import assign_perm
from rest_framework.exceptions import PermissionDenied, ValidationError

from display.default_scorecards.default_scorecard_fai_precision_2020 import get_default_scorecard
from display.models import Contest, NavigationTask, Route, Squadron, SquadronInvitation, SquadronMembership
from display.services import squadrons
from display.services.contest_visibility import (
    audience_contests,
    can_view_contest,
    can_view_navigation_task,
    visible_contests,
)


def make_user(email):
    return get_user_model().objects.create(email=email)


class SquadronTestBase(TestCase):
    def setUp(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        self.contest = Contest.objects.create(
            name="Private", start_time=now, finish_time=now + datetime.timedelta(days=1), location="60, 11"
        )
        self.task = NavigationTask.create(
            name="Private task",
            original_scorecard=get_default_scorecard(),
            route=Route.objects.create(name="Route"),
            contest=self.contest,
            start_time=now,
            finish_time=now + datetime.timedelta(days=1),
        )
        self.admin = make_user("admin@example.com")
        self.member = make_user("member@example.com")
        self.outsider = make_user("outsider@example.com")
        self.organiser = make_user("organiser@example.com")
        for permission in ("view_contest", "change_contest"):
            assign_perm(permission, self.organiser, self.contest)
        self.squadron = squadrons.create_squadron(self.admin, "Østlandet", "Friends flying together")
        SquadronMembership.objects.create(squadron=self.squadron, user=self.member)


class TestSquadronAudience(SquadronTestBase):
    def test_nobody_sees_a_private_contest_before_it_is_shared(self):
        self.assertFalse(can_view_contest(self.member, self.contest))
        self.assertFalse(can_view_navigation_task(self.member, self.task))

    def test_members_of_a_squadron_the_contest_is_shared_with_are_in_its_audience(self):
        self.contest.shared_with_squadrons.add(self.squadron)
        for user in (self.admin, self.member):
            self.assertTrue(can_view_contest(user, self.contest), user)
            self.assertTrue(can_view_navigation_task(user, self.task), user)
            self.assertEqual(set(audience_contests(user)), {self.contest})
            self.assertIn(self.contest, visible_contests(user))
        self.assertFalse(can_view_contest(self.outsider, self.contest))
        self.assertFalse(can_view_navigation_task(self.outsider, self.task))
        self.assertNotIn(self.contest, visible_contests(self.outsider))
        self.assertNotIn(self.contest, visible_contests(None))

    def test_leaving_the_squadron_ends_the_access(self):
        self.contest.shared_with_squadrons.add(self.squadron)
        squadrons.remove_member(self.squadron, self.member, squadrons.membership_of(self.squadron, self.member))
        self.assertFalse(can_view_contest(self.member, self.contest))

    def test_unsharing_ends_the_access(self):
        self.contest.shared_with_squadrons.add(self.squadron)
        squadrons.unshare_contest(self.contest, self.squadron, self.organiser)
        self.assertFalse(can_view_contest(self.member, self.contest))

    def test_membership_gives_no_right_to_manage(self):
        self.contest.shared_with_squadrons.add(self.squadron)
        self.assertFalse(self.member.has_perm("display.change_contest", self.contest))
        self.assertFalse(self.admin.has_perm("display.change_contest", self.contest))

    def test_a_member_opens_the_private_task_over_the_api(self):
        self.contest.shared_with_squadrons.add(self.squadron)
        url = f"/api/v1/contests/{self.contest.pk}/navigationtasks/{self.task.pk}/"
        self.client.force_login(self.outsider)
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.force_login(self.member)
        self.assertEqual(self.client.get(url).status_code, 200)
        names = {contest["name"] for contest in self.client.get("/api/v1/contests/").json()["results"]}
        self.assertIn("Private", names)


class TestSquadronSharing(SquadronTestBase):
    def test_a_member_who_manages_the_contest_shares_it(self):
        assign_perm("view_contest", self.member, self.contest)
        assign_perm("change_contest", self.member, self.contest)
        squadrons.share_contest(self.contest, self.squadron, self.member)
        self.assertEqual(list(self.contest.shared_with_squadrons.all()), [self.squadron])

    def test_sharing_needs_the_right_to_manage_the_contest(self):
        with self.assertRaises(PermissionDenied):
            squadrons.share_contest(self.contest, self.squadron, self.member)

    def test_sharing_needs_membership_of_the_squadron(self):
        with self.assertRaises(PermissionDenied):
            squadrons.share_contest(self.contest, self.squadron, self.organiser)

    def test_stopping_sharing_is_for_the_squadron_admin_the_sharer_and_the_contests_managers(self):
        self.contest.shared_with_squadrons.add(self.squadron)
        with self.assertRaises(PermissionDenied):
            squadrons.unshare_contest(self.contest, self.squadron, self.outsider)
        with self.assertRaises(PermissionDenied):
            squadrons.unshare_contest(self.contest, self.squadron, self.member)  # in the squadron, did not share it
        squadrons.unshare_contest(self.contest, self.squadron, self.admin)
        self.assertFalse(self.contest.shared_with_squadrons.exists())


class TestSquadronInvitations(SquadronTestBase):
    def test_creating_a_squadron_makes_the_creator_its_admin(self):
        self.assertTrue(squadrons.is_admin(self.squadron, self.admin))
        self.assertFalse(squadrons.is_admin(self.squadron, self.member))

    def test_an_invited_user_joins_by_accepting(self):
        invitation = squadrons.invite(self.squadron, self.admin, "Outsider@Example.com")
        self.assertEqual(invitation.email, "outsider@example.com")
        self.assertIsNone(squadrons.membership_of(self.squadron, self.outsider))
        self.assertEqual(list(squadrons.pending_invitations_for(self.outsider)), [invitation])
        squadrons.accept_invitation(invitation, self.outsider)
        self.assertEqual(squadrons.membership_of(self.squadron, self.outsider).role, SquadronMembership.MEMBER)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, SquadronInvitation.ACCEPTED)
        self.assertEqual(list(squadrons.pending_invitations_for(self.outsider)), [])

    def test_inviting_by_user_id_uses_the_users_address(self):
        invitation = squadrons.invite(self.squadron, self.admin, str(self.outsider.pk))
        self.assertEqual(invitation.email, "outsider@example.com")

    def test_an_invitation_as_admin_gives_the_admin_role_once_accepted(self):
        invitation = squadrons.invite(self.squadron, self.admin, "outsider@example.com", SquadronMembership.ADMIN)
        squadrons.accept_invitation(invitation, self.outsider)
        self.assertTrue(squadrons.is_admin(self.squadron, self.outsider))

    def test_a_declined_invitation_gives_nothing(self):
        invitation = squadrons.invite(self.squadron, self.admin, "outsider@example.com")
        squadrons.decline_invitation(invitation, self.outsider)
        self.assertIsNone(squadrons.membership_of(self.squadron, self.outsider))
        with self.assertRaises(PermissionDenied):
            squadrons.accept_invitation(invitation, self.outsider)

    def test_only_the_invited_user_may_answer(self):
        invitation = squadrons.invite(self.squadron, self.admin, "outsider@example.com")
        with self.assertRaises(PermissionDenied):
            squadrons.accept_invitation(invitation, self.member)
        with self.assertRaises(PermissionDenied):
            squadrons.decline_invitation(invitation, self.member)

    def test_a_revoked_invitation_cannot_be_accepted(self):
        invitation = squadrons.invite(self.squadron, self.admin, "outsider@example.com")
        squadrons.revoke_invitation(invitation, self.admin)
        with self.assertRaises(PermissionDenied):
            squadrons.accept_invitation(invitation, self.outsider)

    def test_only_admins_invite_and_revoke(self):
        with self.assertRaises(PermissionDenied):
            squadrons.invite(self.squadron, self.member, "outsider@example.com")
        invitation = squadrons.invite(self.squadron, self.admin, "outsider@example.com")
        with self.assertRaises(PermissionDenied):
            squadrons.revoke_invitation(invitation, self.member)

    def test_no_double_invitations_and_no_inviting_members(self):
        squadrons.invite(self.squadron, self.admin, "outsider@example.com")
        with self.assertRaises(ValidationError):
            squadrons.invite(self.squadron, self.admin, "outsider@example.com")
        with self.assertRaises(ValidationError):
            squadrons.invite(self.squadron, self.admin, "member@example.com")

    def test_a_declined_user_can_be_invited_again(self):
        invitation = squadrons.invite(self.squadron, self.admin, "outsider@example.com")
        squadrons.decline_invitation(invitation, self.outsider)
        squadrons.invite(self.squadron, self.admin, "outsider@example.com")

    def test_bad_identifiers_are_rejected(self):
        for identifier in ("not an address", "999999", ""):
            with self.subTest(identifier=identifier), self.assertRaises(ValidationError):
                squadrons.invite(self.squadron, self.admin, identifier)

    def test_an_invitation_reaches_a_user_who_signs_up_later(self):
        invitation = squadrons.invite(self.squadron, self.admin, "later@example.com")
        later = make_user("later@example.com")
        self.assertEqual(list(squadrons.pending_invitations_for(later)), [invitation])


class TestSquadronMembers(SquadronTestBase):
    def test_the_last_admin_can_neither_leave_nor_be_demoted(self):
        admin_membership = squadrons.membership_of(self.squadron, self.admin)
        with self.assertRaises(ValidationError):
            squadrons.remove_member(self.squadron, self.admin, admin_membership)
        with self.assertRaises(ValidationError):
            squadrons.change_role(self.squadron, self.admin, admin_membership, SquadronMembership.MEMBER)

    def test_an_admin_can_leave_once_there_is_another(self):
        squadrons.change_role(
            self.squadron, self.admin, squadrons.membership_of(self.squadron, self.member), SquadronMembership.ADMIN
        )
        squadrons.remove_member(self.squadron, self.admin, squadrons.membership_of(self.squadron, self.admin))
        self.assertIsNone(squadrons.membership_of(self.squadron, self.admin))

    def test_a_member_may_leave_but_not_remove_others(self):
        other = make_user("other@example.com")
        SquadronMembership.objects.create(squadron=self.squadron, user=other)
        with self.assertRaises(PermissionDenied):
            squadrons.remove_member(self.squadron, self.member, squadrons.membership_of(self.squadron, other))
        squadrons.remove_member(self.squadron, self.member, squadrons.membership_of(self.squadron, self.member))
        self.assertIsNone(squadrons.membership_of(self.squadron, self.member))

    def test_an_admin_removes_a_member(self):
        squadrons.remove_member(self.squadron, self.admin, squadrons.membership_of(self.squadron, self.member))
        self.assertIsNone(squadrons.membership_of(self.squadron, self.member))

    def test_only_admins_change_roles_and_delete(self):
        with self.assertRaises(PermissionDenied):
            squadrons.change_role(
                self.squadron, self.member, squadrons.membership_of(self.squadron, self.member), SquadronMembership.ADMIN
            )
        with self.assertRaises(PermissionDenied):
            squadrons.delete_squadron(self.squadron, self.member)
        squadrons.delete_squadron(self.squadron, self.admin)
        self.assertFalse(Squadron.objects.filter(pk=self.squadron.pk).exists())

    def test_deleting_a_squadron_ends_the_access_it_gave(self):
        self.contest.shared_with_squadrons.add(self.squadron)
        squadrons.delete_squadron(self.squadron, self.admin)
        self.assertFalse(can_view_contest(self.member, self.contest))


class TestSquadronContestOwnership(SquadronTestBase):
    """A member may stop sharing only the contests they shared themselves; an admin any."""

    def setUp(self):
        super().setUp()
        now = datetime.datetime.now(datetime.timezone.utc)
        self.other_contest = Contest.objects.create(
            name="Other", start_time=now, finish_time=now + datetime.timedelta(days=1), location="60, 11"
        )
        for user in (self.member, self.admin):
            for contest in (self.contest, self.other_contest):
                for permission in ("view_contest", "change_contest"):
                    assign_perm(permission, user, contest)

    def test_the_share_remembers_who_shared_it(self):
        share = squadrons.share_contest(self.contest, self.squadron, self.member)
        self.assertEqual(share.shared_by, self.member)
        self.assertEqual(squadrons.share_contest(self.contest, self.squadron, self.admin).pk, share.pk)
        share.refresh_from_db()
        self.assertEqual(share.shared_by, self.member, "sharing again changes nothing")

    def test_a_member_stops_sharing_what_they_shared(self):
        squadrons.share_contest(self.contest, self.squadron, self.member)
        squadrons.unshare_contest(self.contest, self.squadron, self.member)
        self.assertFalse(self.contest.shared_with_squadrons.exists())

    def test_a_member_cannot_stop_sharing_what_somebody_else_shared(self):
        # The admin shared both; the member also manages the contest, but the share is not theirs
        squadrons.share_contest(self.contest, self.squadron, self.admin)
        other_member = make_user("other@example.com")
        SquadronMembership.objects.create(squadron=self.squadron, user=other_member)
        with self.assertRaises(PermissionDenied):
            squadrons.unshare_contest(self.contest, self.squadron, other_member)
        self.assertTrue(self.contest.shared_with_squadrons.exists())

    def test_an_admin_stops_sharing_anything(self):
        squadrons.share_contest(self.contest, self.squadron, self.member)
        squadrons.unshare_contest(self.contest, self.squadron, self.admin)
        self.assertFalse(self.contest.shared_with_squadrons.exists())

    def test_an_admin_without_rights_on_the_contest_can_still_remove_it(self):
        outsider_admin = make_user("outsider-admin@example.com")
        SquadronMembership.objects.create(
            squadron=self.squadron, user=outsider_admin, role=SquadronMembership.ADMIN
        )
        squadrons.share_contest(self.contest, self.squadron, self.member)
        squadrons.unshare_contest(self.contest, self.squadron, outsider_admin)
        self.assertFalse(self.contest.shared_with_squadrons.exists())

    def test_whoever_manages_the_contest_can_always_take_it_back(self):
        squadrons.share_contest(self.contest, self.squadron, self.member)
        squadrons.unshare_contest(self.contest, self.squadron, self.organiser)  # manages it, not in the squadron
        self.assertFalse(self.contest.shared_with_squadrons.exists())

    def test_the_sharer_who_left_the_squadron_cannot_remove_it_as_a_member_but_can_as_the_contests_manager(self):
        squadrons.share_contest(self.contest, self.squadron, self.member)
        squadrons.remove_member(self.squadron, self.member, squadrons.membership_of(self.squadron, self.member))
        self.assertTrue(self.contest.shared_with_squadrons.exists(), "leaving does not take the contest back")
        squadrons.unshare_contest(self.contest, self.squadron, self.member)
        self.assertFalse(self.contest.shared_with_squadrons.exists())

    def test_the_contests_a_user_can_open_through_squadrons_list_every_squadron_giving_the_access(self):
        second = squadrons.create_squadron(self.member, "Second")
        squadrons.share_contest(self.contest, self.squadron, self.member)
        squadrons.share_contest(self.contest, second, self.member)
        squadrons.share_contest(self.other_contest, second, self.member)
        access = {
            entry["name"]: sorted(s["name"] for s in entry["squadrons"])
            for entry in squadrons.contest_access_through_squadrons(self.member)
        }
        self.assertEqual(access, {"Private": ["Second", "Østlandet"], "Other": ["Second"]})
        self.assertEqual(squadrons.contest_access_through_squadrons(self.outsider), [])

    def test_only_contests_the_user_manages_and_that_are_not_shared_yet_can_be_added(self):
        squadrons.share_contest(self.contest, self.squadron, self.member)
        self.assertEqual(list(squadrons.shareable_contests(self.squadron, self.member)), [self.other_contest])
        self.assertEqual(list(squadrons.shareable_contests(self.squadron, self.outsider)), [])
