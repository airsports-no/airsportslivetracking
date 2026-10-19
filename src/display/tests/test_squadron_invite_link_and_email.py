"""The squadron invite link, and the e-mail that goes out with an invitation."""

from unittest.mock import patch

from django.core import mail
from guardian.shortcuts import assign_perm
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from display.models import SquadronInvitation, SquadronMembership
from display.services import squadrons
from display.services.squadron_emails import send_squadron_invitation_email
from display.tests.test_squadrons import SquadronTestBase, make_user
from display.tests.test_squadrons_api import SquadronApiTestBase


class TestInviteLink(SquadronTestBase):
    def test_the_link_is_off_until_an_admin_switches_it_on(self):
        self.assertIsNone(self.squadron.invite_token)
        with self.assertRaises(NotFound):
            squadrons.squadron_for_invite_token("anything")
        token = squadrons.enable_invite_link(self.squadron, self.admin)
        self.assertGreaterEqual(len(token), 24)
        self.assertEqual(squadrons.squadron_for_invite_token(token), self.squadron)

    def test_only_admins_control_the_link(self):
        with self.assertRaises(PermissionDenied):
            squadrons.enable_invite_link(self.squadron, self.member)
        squadrons.enable_invite_link(self.squadron, self.admin)
        with self.assertRaises(PermissionDenied):
            squadrons.disable_invite_link(self.squadron, self.member)

    def test_a_new_link_replaces_the_old_and_switching_off_ends_it(self):
        old = squadrons.enable_invite_link(self.squadron, self.admin)
        new = squadrons.enable_invite_link(self.squadron, self.admin)
        self.assertNotEqual(old, new)
        with self.assertRaises(NotFound):
            squadrons.squadron_for_invite_token(old)
        squadrons.disable_invite_link(self.squadron, self.admin)
        with self.assertRaises(NotFound):
            squadrons.squadron_for_invite_token(new)

    def test_joining_makes_a_member_never_an_admin(self):
        token = squadrons.enable_invite_link(self.squadron, self.admin)
        membership = squadrons.join_by_invite_link(token, self.outsider)
        self.assertEqual(membership.role, SquadronMembership.MEMBER)

    def test_joining_again_changes_nothing_and_does_not_demote_an_admin(self):
        token = squadrons.enable_invite_link(self.squadron, self.admin)
        squadrons.join_by_invite_link(token, self.admin)
        self.assertTrue(squadrons.is_admin(self.squadron, self.admin))
        self.assertEqual(SquadronMembership.objects.filter(squadron=self.squadron, user=self.admin).count(), 1)

    def test_joining_answers_an_invitation_to_the_same_address(self):
        invitation = squadrons.invite(self.squadron, self.admin, "outsider@example.com")
        squadrons.join_by_invite_link(squadrons.enable_invite_link(self.squadron, self.admin), self.outsider)
        invitation.refresh_from_db()
        self.assertEqual(invitation.status, SquadronInvitation.ACCEPTED)

    def test_a_dead_link_does_not_join(self):
        with self.assertRaises(NotFound):
            squadrons.join_by_invite_link("nope", self.outsider)


class TestInviteLinkApi(SquadronApiTestBase):
    def test_only_admins_see_the_token(self):
        squadrons.enable_invite_link(self.squadron, self.admin)
        self.login(self.member)
        self.assertIsNone(self.client.get(f"/api/v1/squadrons/{self.squadron.pk}/").json()["invite_token"])
        self.login(self.admin)
        self.assertTrue(self.client.get(f"/api/v1/squadrons/{self.squadron.pk}/").json()["invite_token"])

    def test_the_admin_switches_the_link_on_regenerates_and_off(self):
        self.login(self.admin)
        url = f"/api/v1/squadrons/{self.squadron.pk}/invite-link/"
        first = self.client.post(url).json()["invite_token"]
        second = self.client.post(url).json()["invite_token"]
        self.assertNotEqual(first, second)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertIsNone(self.client.get(f"/api/v1/squadrons/{self.squadron.pk}/").json()["invite_token"])

    def test_a_member_cannot_switch_the_link_on(self):
        self.login(self.member)
        self.assertEqual(self.client.post(f"/api/v1/squadrons/{self.squadron.pk}/invite-link/").status_code, 403)

    def test_a_logged_in_user_previews_and_joins(self):
        token = squadrons.enable_invite_link(self.squadron, self.admin)
        self.login(self.outsider)
        preview = self.client.get(f"/api/v1/squadron_join/{token}/").json()
        self.assertEqual(preview["name"], "Østlandet")
        self.assertEqual(preview["member_count"], 2)
        self.assertFalse(preview["already_member"])
        self.assertNotIn("id", preview, "nothing that identifies the squadron before joining")
        joined = self.client.post(f"/api/v1/squadron_join/{token}/join/")
        self.assertEqual(joined.status_code, 200, joined.content)
        self.assertEqual(joined.json(), {"id": self.squadron.pk, "my_role": "member"})
        self.assertTrue(self.client.get(f"/api/v1/squadron_join/{token}/").json()["already_member"])

    def test_nobody_sees_anything_without_logging_in(self):
        token = squadrons.enable_invite_link(self.squadron, self.admin)
        self.assertIn(self.client.get(f"/api/v1/squadron_join/{token}/").status_code, (401, 403))
        self.assertIn(self.client.post(f"/api/v1/squadron_join/{token}/join/").status_code, (401, 403))

    def test_a_dead_link_is_a_404(self):
        self.login(self.outsider)
        self.assertEqual(self.client.get("/api/v1/squadron_join/wrong/").status_code, 404)
        self.assertEqual(self.client.post("/api/v1/squadron_join/wrong/join/").status_code, 404)
        token = squadrons.enable_invite_link(self.squadron, self.admin)
        squadrons.disable_invite_link(self.squadron, self.admin)
        self.assertEqual(self.client.post(f"/api/v1/squadron_join/{token}/join/").status_code, 404)
        self.assertIsNone(squadrons.membership_of(self.squadron, self.outsider))


class TestInvitationEmail(SquadronTestBase):
    def test_the_mail_goes_to_the_invited_address_and_names_the_squadron_and_the_inviter(self):
        self.admin.first_name, self.admin.last_name = "Anna", "Admin"
        self.admin.save()
        invitation = squadrons.invite(self.squadron, self.admin, "new.person@example.com")
        self.assertTrue(send_squadron_invitation_email(invitation))
        message = mail.outbox[0]
        self.assertEqual(message.to, ["new.person@example.com"])
        self.assertIn("Anna Admin invited you to the squadron Østlandet", message.subject)
        self.assertIn("https://app.airsports.no/squadrons", message.body)
        self.assertIn("Friends flying together", message.body)
        self.assertIn("new.person@example.com", message.body)
        self.assertNotIn("as an admin", message.body)

    def test_an_admin_invitation_says_so(self):
        invitation = squadrons.invite(self.squadron, self.admin, "new@example.com", SquadronMembership.ADMIN)
        send_squadron_invitation_email(invitation)
        self.assertIn("as an admin", mail.outbox[0].body)

    def test_nothing_is_sent_for_an_invitation_that_is_no_longer_open(self):
        invitation = squadrons.invite(self.squadron, self.admin, "outsider@example.com")
        squadrons.decline_invitation(invitation, self.outsider)
        self.assertFalse(send_squadron_invitation_email(invitation))
        self.assertEqual(mail.outbox, [])

    def test_names_cannot_inject_markup_into_the_mail(self):
        self.squadron.name = "<script>alert(1)</script>"
        self.squadron.description = '<a href="https://evil.example">click</a>'
        self.squadron.save()
        invitation = squadrons.invite(self.squadron, self.admin, "new@example.com")
        send_squadron_invitation_email(invitation)
        html = mail.outbox[0].alternatives[0][0]
        self.assertNotIn("<script>", html)
        self.assertNotIn('href="https://evil.example"', html)

    def test_inviting_queues_the_mail_once_the_invitation_is_saved(self):
        with patch("display.tasks.send_squadron_invitation_email_task.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                invitation = squadrons.invite(self.squadron, self.admin, "new@example.com")
        delay.assert_called_once_with(invitation.pk)

    def test_a_failed_invitation_queues_no_mail(self):
        with patch("display.tasks.send_squadron_invitation_email_task.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                with self.assertRaises(ValidationError):
                    squadrons.invite(self.squadron, self.admin, "member@example.com")  # already in
        delay.assert_not_called()

    def test_the_task_survives_a_mail_failure(self):
        from display.tasks import send_squadron_invitation_email_task

        invitation = squadrons.invite(self.squadron, self.admin, "new@example.com")
        with patch("display.services.squadron_emails.send_mail", side_effect=OSError("smtp down")):
            send_squadron_invitation_email_task(invitation.pk)  # logs, does not raise
        send_squadron_invitation_email_task(0)  # an invitation that no longer exists


class TestInvitationLimit(SquadronTestBase):
    def test_a_squadron_cannot_have_unlimited_open_invitations(self):
        with patch.object(squadrons, "MAX_PENDING_INVITATIONS", 3):
            for number in range(3):
                squadrons.invite(self.squadron, self.admin, f"person{number}@example.com")
            with self.assertRaises(ValidationError):
                squadrons.invite(self.squadron, self.admin, "one-too-many@example.com")
            # answered invitations do not count
            first = SquadronInvitation.objects.filter(squadron=self.squadron).first()
            squadrons.revoke_invitation(first, self.admin)
            squadrons.invite(self.squadron, self.admin, "one-too-many@example.com")


class TestReviewFixes(SquadronTestBase):
    """Found in the review of the squadron PR."""

    def test_joining_by_link_leaves_an_admin_invitation_open_so_that_accepting_it_promotes(self):
        admin_invitation = squadrons.invite(self.squadron, self.admin, "outsider@example.com", SquadronMembership.ADMIN)
        squadrons.join_by_invite_link(squadrons.enable_invite_link(self.squadron, self.admin), self.outsider)
        admin_invitation.refresh_from_db()
        self.assertEqual(admin_invitation.status, SquadronInvitation.PENDING)
        self.assertFalse(squadrons.is_admin(self.squadron, self.outsider))
        squadrons.accept_invitation(admin_invitation, self.outsider)
        self.assertTrue(squadrons.is_admin(self.squadron, self.outsider))

    def test_nobody_sends_more_than_the_daily_limit_across_squadrons_also_when_cancelled(self):
        other_squadron = squadrons.create_squadron(self.admin, "Second")
        with patch.object(squadrons, "MAX_INVITATIONS_PER_USER_PER_DAY", 3):
            first = squadrons.invite(self.squadron, self.admin, "a@example.com")
            squadrons.invite(other_squadron, self.admin, "b@example.com")
            squadrons.revoke_invitation(first, self.admin)  # cancelling gives nothing back
            squadrons.invite(self.squadron, self.admin, "c@example.com")
            with self.assertRaises(ValidationError):
                squadrons.invite(other_squadron, self.admin, "d@example.com")

    def test_the_limit_is_per_person(self):
        squadrons.invite(self.squadron, self.admin, "a@example.com")
        with patch.object(squadrons, "MAX_INVITATIONS_PER_USER_PER_DAY", 1):
            with self.assertRaises(ValidationError):
                squadrons.invite(self.squadron, self.admin, "b@example.com")
            other = make_user("other-admin@example.com")
            other_squadron = squadrons.create_squadron(other, "Other")
            squadrons.invite(other_squadron, other, "b@example.com")

    def test_inviting_an_address_again_soon_after_cancelling_is_not_mailed_again(self):
        with patch("display.tasks.send_squadron_invitation_email_task.delay") as delay:
            with self.captureOnCommitCallbacks(execute=True):
                first = squadrons.invite(self.squadron, self.admin, "new@example.com")
            squadrons.revoke_invitation(first, self.admin)
            with self.captureOnCommitCallbacks(execute=True):
                second = squadrons.invite(self.squadron, self.admin, "new@example.com")
        delay.assert_called_once_with(first.pk)
        self.assertEqual(second.status, SquadronInvitation.PENDING, "the invitation is still made and shown in the app")


class TestContestListFollowsSquadrons(SquadronApiTestBase):
    """The contest list is cached per user: joining, leaving and sharing change what is in it."""

    def names(self):
        return {contest["name"] for contest in self.client.get("/api/v1/contests/").json()["results"]}

    def test_the_list_follows_membership_and_sharing(self):
        self.login(self.outsider)
        self.assertNotIn("Private", self.names())  # fills the cache for this user

        token = squadrons.enable_invite_link(self.squadron, self.admin)
        squadrons.join_by_invite_link(token, self.outsider)
        self.assertNotIn("Private", self.names(), "a member of a squadron without the contest")

        for permission in ("view_contest", "change_contest"):
            assign_perm(permission, self.admin, self.contest)
        squadrons.share_contest(self.contest, self.squadron, self.admin)
        self.assertIn("Private", self.names(), "shared with the squadron")

        squadrons.unshare_contest(self.contest, self.squadron, self.admin)
        self.assertNotIn("Private", self.names(), "stopped sharing")

        squadrons.share_contest(self.contest, self.squadron, self.admin)
        self.assertIn("Private", self.names())
        squadrons.remove_member(self.squadron, self.outsider, squadrons.membership_of(self.squadron, self.outsider))
        self.assertNotIn("Private", self.names(), "left the squadron")


class TestUnshareAnswer(SquadronApiTestBase):
    def test_only_the_contests_managers_are_told_what_else_it_is_shared_with(self):
        second = squadrons.create_squadron(self.admin, "Second")
        for permission in ("view_contest", "change_contest"):
            assign_perm(permission, self.organiser, self.contest)
        self.contest.shared_with_squadrons.through.objects.create(
            squadron=self.squadron, contest=self.contest, shared_by=self.member
        )
        self.contest.shared_with_squadrons.through.objects.create(
            squadron=second, contest=self.contest, shared_by=self.member
        )

        # The squadron's admin does not manage the contest: allowed to take it away, told nothing about the rest
        self.login(self.admin)
        answer = self.client.delete(f"/api/v1/contests/{self.contest.pk}/squadrons/{self.squadron.pk}/")
        self.assertEqual(answer.status_code, 204, answer.content)
        self.assertEqual(list(self.contest.shared_with_squadrons.all()), [second])

        # The contest's manager gets the whole list
        self.login(self.organiser)
        answer = self.client.delete(f"/api/v1/contests/{self.contest.pk}/squadrons/{second.pk}/")
        self.assertEqual(answer.status_code, 200, answer.content)
        self.assertEqual(answer.json(), [])


class TestContestListFollowsDirectGrants(SquadronApiTestBase):
    """A view grant given or taken away by an organiser shows in the cached contest list at once."""

    def names(self):
        return {contest["name"] for contest in self.client.get("/api/v1/contests/").json()["results"]}

    def test_the_list_follows_the_grants_on_a_contest(self):
        from display.services.contest_permissions import set_contest_permission_level

        self.login(self.outsider)
        self.assertNotIn("Private", self.names())  # fills the cache for this user

        set_contest_permission_level(self.contest, self.outsider, "view", self.organiser)
        self.assertIn("Private", self.names(), "given the right to view")

        set_contest_permission_level(self.contest, self.outsider, "nothing", self.organiser)
        self.assertNotIn("Private", self.names(), "taken away again")

    def test_the_list_follows_a_grant_made_directly_with_guardian(self):
        self.login(self.outsider)
        self.assertNotIn("Private", self.names())
        assign_perm("view_contest", self.outsider, self.contest)
        self.assertIn("Private", self.names())
