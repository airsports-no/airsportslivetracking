"""
Type-ahead people search (display.services.people_search / GET /display/api/people/search/).
The contract that matters most is what it does NOT reveal: no email addresses, nothing for very
short queries, and a masked hint only when two people are otherwise indistinguishable.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from display.models import Person
from display.services.people_search import mask_email_heavily

URL = "/display/api/people/search/"


class TestMaskEmail(TestCase):
    def test_masks_local_part_and_domain(self):
        self.assertEqual(mask_email_heavily("frank@example.com"), "f****@***.com")

    def test_tolerates_garbage(self):
        self.assertEqual(mask_email_heavily(""), "")
        self.assertEqual(mask_email_heavily("not-an-email"), "")


class PeopleSearchBase(TestCase):
    def setUp(self):
        cache.clear()  # the throttle counts per user in the cache
        self.user = get_user_model().objects.create_user(
            email="me@example.com", password="secret", first_name="Me", last_name="Myself"
        )
        self.me = Person.objects.create(first_name="Me", last_name="Myself", email="me@example.com")
        self.client.force_login(self.user)

    def search(self, query, **params):
        return self.client.get(URL, {"q": query, **params})


class TestPersonSearch(PeopleSearchBase):
    def setUp(self):
        super().setUp()
        self.anna = Person.objects.create(first_name="Anna", last_name="Hansen", email="anna@example.com")
        self.annabel = Person.objects.create(first_name="Annabel", last_name="Berg", email="annabel@example.com")
        self.bo = Person.objects.create(first_name="Bo", last_name="Andersen", email="bo@example.com")

    def test_requires_login(self):
        self.client.logout()
        self.assertIn(self.search("anna").status_code, (401, 403))

    def test_short_query_returns_nothing(self):
        self.assertEqual(self.search("an").json(), [])
        self.assertEqual(self.search("  ").json(), [])

    def test_finds_by_first_or_last_name_case_insensitively(self):
        ids = {r["id"] for r in self.search("HANSEN").json()}
        self.assertEqual(ids, {self.anna.id})

    def test_multi_word_query_must_match_every_word(self):
        ids = {r["id"] for r in self.search("anna berg").json()}
        self.assertEqual(ids, {self.annabel.id})

    def test_prefix_matches_rank_first(self):
        # "ander" is a prefix of Bo Andersen's last name and only a substring elsewhere
        Person.objects.create(first_name="Xander", last_name="Aaa", email="xander@example.com")
        ids = [r["id"] for r in self.search("ander").json()]
        self.assertEqual(ids[0], self.bo.id)

    def test_never_returns_an_email(self):
        for result in self.search("anna").json():
            self.assertEqual(set(result), {"id", "name", "country", "picture", "email_hint"})
            self.assertNotIn("@example.com", str(result))

    def test_no_hint_when_name_is_unique(self):
        self.assertEqual([r["email_hint"] for r in self.search("hansen").json()], [""])

    def test_masked_hint_for_namesakes(self):
        Person.objects.create(first_name="Anna", last_name="Hansen", email="other.anna@gmail.com")
        results = self.search("hansen").json()
        self.assertEqual(len(results), 2)
        self.assertEqual({r["email_hint"] for r in results}, {"a***@***.com", "o********@***.com"})

    def test_country_separates_namesakes_without_a_hint(self):
        self.anna.country = "NO"
        self.anna.save()
        Person.objects.create(first_name="Anna", last_name="Hansen", email="other.anna@gmail.com", country="SE")
        results = self.search("hansen").json()
        self.assertEqual({r["country"] for r in results}, {"Norway", "Sweden"})
        self.assertEqual({r["email_hint"] for r in results}, {""})

    def test_exact_email_resolves_one_person_without_a_hint(self):
        results = self.search("Anna@Example.com").json()
        self.assertEqual([r["id"] for r in results], [self.anna.id])
        self.assertEqual(results[0]["email_hint"], "")

    def test_partial_email_does_not_match(self):
        self.assertEqual(self.search("anna@exam").json(), [])

    def test_excludes_self_by_default_and_can_include(self):
        self.assertEqual(self.search("myself").json(), [])
        self.assertEqual([r["id"] for r in self.search("myself", exclude_self="false").json()], [self.me.id])

    def test_results_are_capped(self):
        for i in range(15):
            Person.objects.create(first_name="Many", last_name=f"Match{i:02d}", email=f"many{i}@example.com")
        self.assertEqual(len(self.search("many").json()), 10)

    def test_unknown_kind_is_rejected(self):
        self.assertEqual(self.search("anna", kind="everything").status_code, 400)


class TestUserSearch(PeopleSearchBase):
    def setUp(self):
        super().setUp()
        User = get_user_model()
        self.with_account = User.objects.create_user(
            email="kari@example.com", password="x", first_name="Kari", last_name="Nordmann"
        )
        # Person without an account must not be offered as a permission target
        Person.objects.create(first_name="Kari", last_name="Utenkonto", email="noaccount@example.com")
        # Account with a blank name, found through its Person record
        self.blank_name = User.objects.create_user(email="ola@example.com", password="x")
        Person.objects.create(first_name="Ola", last_name="Nordmann", email="ola@example.com")

    def search_users(self, query):
        return self.search(query, kind="user")

    def test_only_accounts_are_returned(self):
        ids = {r["id"] for r in self.search_users("kari").json()}
        self.assertEqual(ids, {self.with_account.pk})

    def test_result_id_is_the_user_pk_and_not_the_person_pk(self):
        result = self.search_users("nordmann").json()
        self.assertIn(self.with_account.pk, {r["id"] for r in result})

    def test_blank_account_name_is_found_via_person_name(self):
        results = self.search_users("ola").json()
        self.assertEqual([r["id"] for r in results], [self.blank_name.pk])
        self.assertEqual(results[0]["name"], "Ola Nordmann")

    def test_never_offers_yourself(self):
        self.assertEqual(self.search_users("myself").json(), [])

    def test_exact_email_finds_the_account(self):
        self.assertEqual([r["id"] for r in self.search_users("KARI@example.com").json()], [self.with_account.pk])
        self.assertEqual(self.search_users("noaccount@example.com").json(), [])

    def test_never_returns_an_email(self):
        self.assertNotIn("@example.com", str(self.search_users("nordmann").json()))
