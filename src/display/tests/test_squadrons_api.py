"""The squadron REST API: access, invitations, members and sharing a contest."""

from django.urls import reverse
from guardian.shortcuts import assign_perm
from rest_framework import status
from rest_framework.test import APIClient

from display.models import SquadronMembership
from display.services import squadrons
from display.tests.test_squadrons import SquadronTestBase


class SquadronApiTestBase(SquadronTestBase):
    client_class = APIClient

    def url(self, name, *args):
        return reverse(name, args=args)

    def login(self, user):
        self.client.force_login(user)


class TestSquadronApi(SquadronApiTestBase):
    def test_anonymous_has_no_access(self):
        self.assertIn(self.client.get("/api/v1/squadrons/").status_code, (401, 403))

    def test_create_makes_the_creator_admin_and_list_shows_only_own_squadrons(self):
        self.login(self.outsider)
        result = self.client.post("/api/v1/squadrons/", {"name": "Night owls"}, format="json")
        self.assertEqual(result.status_code, status.HTTP_201_CREATED, result.content)
        self.assertEqual(result.json()["my_role"], "admin")
        names = [squadron["name"] for squadron in self.client.get("/api/v1/squadrons/").json()]
        self.assertEqual(names, ["Night owls"])

    def test_a_squadron_needs_a_name(self):
        self.login(self.outsider)
        self.assertEqual(self.client.post("/api/v1/squadrons/", {"name": "  "}, format="json").status_code, 400)

    def test_a_non_member_cannot_see_the_squadron_or_its_members(self):
        self.login(self.outsider)
        self.assertEqual(self.client.get(f"/api/v1/squadrons/{self.squadron.pk}/").status_code, 404)

    def test_members_see_the_members_without_addresses_and_only_admins_see_invitations(self):
        squadrons.invite(self.squadron, self.admin, "invited@example.com")
        self.login(self.member)
        detail = self.client.get(f"/api/v1/squadrons/{self.squadron.pk}/").json()
        self.assertEqual(len(detail["members"]), 2)
        self.assertEqual(detail["invitations"], [])
        self.assertNotIn("admin@example.com", str(detail))
        self.login(self.admin)
        detail = self.client.get(f"/api/v1/squadrons/{self.squadron.pk}/").json()
        self.assertEqual(len(detail["invitations"]), 1)
        self.assertNotIn("invited@example.com", str(detail))

    def test_only_admins_edit_and_delete(self):
        url = f"/api/v1/squadrons/{self.squadron.pk}/"
        self.login(self.member)
        self.assertEqual(self.client.patch(url, {"name": "Mine"}, format="json").status_code, 403)
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.login(self.admin)
        self.assertEqual(self.client.patch(url, {"name": "Renamed"}, format="json").status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)


class TestSquadronInvitationApi(SquadronApiTestBase):
    def test_invite_accept_and_leave(self):
        self.login(self.admin)
        result = self.client.post(
            f"/api/v1/squadrons/{self.squadron.pk}/invite/", {"identifier": str(self.outsider.pk)}, format="json"
        )
        self.assertEqual(result.status_code, status.HTTP_201_CREATED, result.content)

        self.login(self.outsider)
        invitations = self.client.get("/api/v1/squadron_invitations/").json()
        self.assertEqual(len(invitations), 1)
        self.assertEqual(invitations[0]["squadron_name"], "Østlandet")
        self.assertEqual(self.client.get("/api/v1/squadrons/").json(), [])

        accepted = self.client.post(f"/api/v1/squadron_invitations/{invitations[0]['id']}/accept/")
        self.assertEqual(accepted.status_code, 204, accepted.content)
        self.assertEqual(self.client.get("/api/v1/squadron_invitations/").json(), [])
        self.assertEqual(len(self.client.get("/api/v1/squadrons/").json()), 1)

        self.assertEqual(self.client.post(f"/api/v1/squadrons/{self.squadron.pk}/leave/").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/squadrons/").json(), [])

    def test_decline(self):
        invitation = squadrons.invite(self.squadron, self.admin, "outsider@example.com")
        self.login(self.outsider)
        self.assertEqual(self.client.post(f"/api/v1/squadron_invitations/{invitation.pk}/decline/").status_code, 204)
        self.assertEqual(self.client.get("/api/v1/squadron_invitations/").json(), [])

    def test_somebody_elses_invitation_does_not_exist_for_you(self):
        invitation = squadrons.invite(self.squadron, self.admin, "outsider@example.com")
        self.login(self.member)
        self.assertEqual(self.client.post(f"/api/v1/squadron_invitations/{invitation.pk}/accept/").status_code, 404)

    def test_members_cannot_invite_and_admins_can_revoke(self):
        self.login(self.member)
        url = f"/api/v1/squadrons/{self.squadron.pk}/invite/"
        self.assertEqual(self.client.post(url, {"identifier": "x@example.com"}, format="json").status_code, 403)
        self.login(self.admin)
        invitation_id = self.client.post(url, {"identifier": "x@example.com"}, format="json").json()["id"]
        revoke = self.client.delete(f"/api/v1/squadrons/{self.squadron.pk}/invitations/{invitation_id}/")
        self.assertEqual(revoke.status_code, 204)

    def test_a_bad_identifier_is_a_400(self):
        self.login(self.admin)
        result = self.client.post(
            f"/api/v1/squadrons/{self.squadron.pk}/invite/", {"identifier": "nonsense"}, format="json"
        )
        self.assertEqual(result.status_code, 400)


class TestSquadronMembersApi(SquadronApiTestBase):
    def test_admin_changes_roles_and_removes_members(self):
        membership = squadrons.membership_of(self.squadron, self.member)
        url = f"/api/v1/squadrons/{self.squadron.pk}/members/{membership.pk}/"
        self.login(self.admin)
        self.assertEqual(self.client.put(url, {"role": "admin"}, format="json").status_code, 200)
        membership.refresh_from_db()
        self.assertEqual(membership.role, SquadronMembership.ADMIN)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_the_last_admin_cannot_leave(self):
        self.login(self.admin)
        self.assertEqual(self.client.post(f"/api/v1/squadrons/{self.squadron.pk}/leave/").status_code, 400)

    def test_a_member_cannot_remove_another(self):
        other = squadrons.membership_of(self.squadron, self.admin)
        self.login(self.member)
        result = self.client.delete(f"/api/v1/squadrons/{self.squadron.pk}/members/{other.pk}/")
        self.assertEqual(result.status_code, 403)


class TestContestSharingApi(SquadronApiTestBase):
    def setUp(self):
        super().setUp()
        for permission in ("view_contest", "change_contest"):
            assign_perm(permission, self.member, self.contest)

    def test_a_member_who_manages_the_contest_shares_and_unshares_it(self):
        self.login(self.member)
        url = f"/api/v1/contests/{self.contest.pk}/squadrons/"
        shared = self.client.post(url, {"squadron": self.squadron.pk}, format="json")
        self.assertEqual(shared.status_code, 200, shared.content)
        self.assertEqual([item["name"] for item in shared.json()], ["Østlandet"])
        self.assertTrue(shared.json()[0]["can_remove"])
        self.assertEqual(self.client.get(url).json(), shared.json())

        self.login(self.admin)  # now in the audience
        self.assertEqual(self.client.get(f"/api/v1/contests/{self.contest.pk}/").status_code, 200)

        self.login(self.member)
        removed = self.client.delete(f"{url}{self.squadron.pk}/")
        self.assertEqual(removed.status_code, 200, removed.content)
        self.assertEqual(removed.json(), [])
        self.login(self.admin)
        self.assertEqual(self.client.get(f"/api/v1/contests/{self.contest.pk}/").status_code, 404)

    def test_the_audience_cannot_share_the_contest_or_see_who_it_is_shared_with(self):
        self.contest.shared_with_squadrons.add(self.squadron)
        self.login(self.admin)  # in the audience through the squadron, not a manager
        url = f"/api/v1/contests/{self.contest.pk}/squadrons/"
        self.assertEqual(self.client.get(url).status_code, 403)
        self.assertEqual(self.client.post(url, {"squadron": self.squadron.pk}, format="json").status_code, 403)

    def test_a_squadron_one_is_not_in_cannot_be_used(self):
        self.login(self.organiser)
        result = self.client.post(
            f"/api/v1/contests/{self.contest.pk}/squadrons/", {"squadron": self.squadron.pk}, format="json"
        )
        self.assertEqual(result.status_code, 404)
        self.assertEqual(self.contest.shared_with_squadrons.count(), 0)


class TestContestSerialisersKeepSharingClosed(SquadronApiTestBase):
    def test_a_contest_cannot_be_shared_by_writing_it_and_it_is_not_in_the_output(self):
        for permission in ("view_contest", "change_contest", "add_contest", "delete_contest"):
            assign_perm(permission, self.organiser, self.contest)
        self.login(self.organiser)
        url = f"/api/v1/contests/{self.contest.pk}/"
        self.assertNotIn("shared_with_squadrons", self.client.get(url).json())
        self.client.patch(url, {"shared_with_squadrons": [self.squadron.pk]}, format="json")
        self.assertEqual(self.contest.shared_with_squadrons.count(), 0)
        self.client.logout()
        self.contest.make_public()
        self.assertNotIn(
            "shared_with_squadrons", self.client.get(f"/api/v1/contests/{self.contest.pk}/results_details/").json()
        )


class TestSquadronsInTheNavbar(SquadronApiTestBase):
    def test_the_link_and_the_invitation_badge_are_for_logged_in_users(self):
        anonymous = self.client.get("/")
        self.assertNotContains(anonymous, 'id="squadron-invitations-badge"')
        self.login(self.member)
        page = self.client.get("/")
        self.assertContains(page, 'id="squadron-invitations-badge"')
        self.assertContains(page, "Squadrons <span")


class TestSquadronContestsApi(SquadronApiTestBase):
    def setUp(self):
        super().setUp()
        for user in (self.member, self.admin):
            for permission in ("view_contest", "change_contest"):
                assign_perm(permission, user, self.contest)

    def test_add_list_and_remove_a_contest_from_the_squadron(self):
        self.login(self.member)
        base = f"/api/v1/squadrons/{self.squadron.pk}/"
        shareable = self.client.get(base + "shareable-contests/").json()
        self.assertEqual([contest["id"] for contest in shareable], [self.contest.pk])

        added = self.client.post(base + "contests/", {"contest": self.contest.pk}, format="json")
        self.assertEqual(added.status_code, 201, added.content)
        self.assertTrue(added.json()["can_remove"])
        self.assertTrue(added.json()["shared_by_me"])
        self.assertEqual(self.client.get(base + "shareable-contests/").json(), [])

        detail = self.client.get(base).json()
        self.assertEqual([contest["id"] for contest in detail["contests"]], [self.contest.pk])
        self.assertEqual(self.client.get("/api/v1/squadrons/").json()[0]["contest_count"], 1)

        self.assertEqual(self.client.delete(base + f"contests/{self.contest.pk}/").status_code, 204)
        self.assertEqual(self.client.get(base).json()["contests"], [])

    def test_a_member_cannot_remove_what_somebody_else_added_but_an_admin_can(self):
        squadrons.share_contest(self.contest, self.squadron, self.admin)
        other_member = make_user_for_squadron(self.squadron, "another@example.com")
        assign_perm("view_contest", other_member, self.contest)
        url = f"/api/v1/squadrons/{self.squadron.pk}/contests/{self.contest.pk}/"
        self.login(other_member)
        entry = self.client.get(f"/api/v1/squadrons/{self.squadron.pk}/").json()["contests"][0]
        self.assertFalse(entry["can_remove"])
        self.assertEqual(self.client.delete(url).status_code, 403)
        self.login(self.admin)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_a_contest_the_user_does_not_manage_cannot_be_added(self):
        self.login(self.member)
        other = self.make_other_contest()
        result = self.client.post(
            f"/api/v1/squadrons/{self.squadron.pk}/contests/", {"contest": other.pk}, format="json"
        )
        self.assertEqual(result.status_code, 404)
        self.assertEqual(other.shared_with_squadrons.count(), 0)

    def test_a_non_member_cannot_use_the_squadron(self):
        self.login(self.organiser)
        base = f"/api/v1/squadrons/{self.squadron.pk}/"
        self.assertEqual(self.client.get(base + "shareable-contests/").status_code, 404)
        self.assertEqual(self.client.post(base + "contests/", {"contest": self.contest.pk}, format="json").status_code, 404)

    def test_contest_access_lists_each_contest_once_with_all_its_squadrons(self):
        second = squadrons.create_squadron(self.member, "Second")
        squadrons.share_contest(self.contest, self.squadron, self.member)
        squadrons.share_contest(self.contest, second, self.member)
        self.login(self.member)
        access = self.client.get("/api/v1/squadrons/contest-access/").json()
        self.assertEqual(len(access), 1)
        self.assertEqual(sorted(s["name"] for s in access[0]["squadrons"]), ["Second", "Østlandet"])
        self.login(self.outsider)
        self.assertEqual(self.client.get("/api/v1/squadrons/contest-access/").json(), [])

    def make_other_contest(self):
        import datetime

        from display.models import Contest

        now = datetime.datetime.now(datetime.timezone.utc)
        return Contest.objects.create(
            name="Not mine", start_time=now, finish_time=now + datetime.timedelta(days=1), location="60, 11"
        )


def make_user_for_squadron(squadron, email):
    from display.tests.test_squadrons import make_user

    user = make_user(email)
    SquadronMembership.objects.create(squadron=squadron, user=user)
    return user
