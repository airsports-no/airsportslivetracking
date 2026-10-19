"""Deleting an account must not leave a squadron that nobody can manage."""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from display.models import Person, Squadron, SquadronInvitation, SquadronMembership
from display.services import squadrons
from display.services.account_deletion import delete_account


def make_user(email):
    user = get_user_model().objects.create(email=email, username=email)
    Person.objects.create(first_name="Some", last_name="One", email=email, validated=True)
    return user


class TestAccountDeletionAndSquadrons(TestCase):
    def setUp(self):
        for target, kwargs in (
            ("display.services.account_deletion._delete_firebase_user", {"return_value": True}),
            ("display.models.MyUser.send_deletion_email", {}),
        ):
            patcher = patch(target, **kwargs)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.admin = make_user("admin@example.com")
        self.early = make_user("early@example.com")
        self.late = make_user("late@example.com")
        self.squadron = squadrons.create_squadron(self.admin, "Østlandet")
        SquadronMembership.objects.create(squadron=self.squadron, user=self.early)
        SquadronMembership.objects.create(squadron=self.squadron, user=self.late)

    def test_the_only_admin_hands_the_squadron_to_the_member_who_has_been_in_it_longest(self):
        delete_account("admin@example.com")
        self.assertTrue(squadrons.is_admin(self.squadron, self.early))
        self.assertFalse(squadrons.is_admin(self.squadron, self.late))
        self.assertEqual(self.squadron.memberships.count(), 2)

    def test_a_squadron_with_nobody_else_goes_with_its_only_member(self):
        alone = squadrons.create_squadron(self.late, "Alone")
        delete_account("late@example.com")
        self.assertFalse(Squadron.objects.filter(pk=alone.pk).exists())

    def test_a_squadron_with_another_admin_is_left_as_it_is(self):
        squadrons.change_role(
            self.squadron, self.admin, squadrons.membership_of(self.squadron, self.late), SquadronMembership.ADMIN
        )
        delete_account("admin@example.com")
        self.assertTrue(squadrons.is_admin(self.squadron, self.late))
        self.assertFalse(squadrons.is_admin(self.squadron, self.early), "nobody else is promoted")

    def test_a_member_leaves_without_changing_anything_for_the_others(self):
        delete_account("early@example.com")
        self.assertTrue(squadrons.is_admin(self.squadron, self.admin))
        self.assertEqual(self.squadron.memberships.count(), 2)

    def test_invitations_waiting_at_the_deleted_address_go_and_the_ones_it_sent_stay(self):
        make_user("waiting@example.com")
        waiting = squadrons.invite(self.squadron, self.admin, "waiting@example.com")
        sent = squadrons.invite(self.squadron, self.admin, "someone@example.com")
        delete_account("waiting@example.com")
        self.assertFalse(SquadronInvitation.objects.filter(pk=waiting.pk).exists())
        self.assertTrue(SquadronInvitation.objects.filter(pk=sent.pk).exists())

    def test_contests_shared_with_the_squadron_stay_shared(self):
        import datetime

        from display.models import Contest

        now = datetime.datetime.now(datetime.timezone.utc)
        contest = Contest.objects.create(
            name="Shared", start_time=now, finish_time=now + datetime.timedelta(days=1), location="60, 11"
        )
        contest.shared_with_squadrons.add(self.squadron)
        delete_account("admin@example.com")
        self.assertEqual(list(contest.shared_with_squadrons.all()), [self.squadron])
