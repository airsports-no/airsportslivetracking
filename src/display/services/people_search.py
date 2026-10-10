"""
Type-ahead search for people, used by the pilot/co-pilot pickers (kind="person": every Person row,
account or not) and the permission pickers (kind="user": accounts only).

The endpoint is deliberately not a directory: queries need at least MIN_QUERY_LENGTH characters,
results are capped, and an email address is never returned - only a heavily masked hint, and only
when two results would otherwise be indistinguishable by name and country. Typing a complete email
address still resolves to exactly that person, so "I know their address" keeps working.
"""

from collections import Counter
from typing import Iterable, Optional

from django.db.models import Q

from display.models import MyUser, Person

MIN_QUERY_LENGTH = 3
MAX_RESULTS = 10
# Candidates fetched before ranking; ranking is done in Python on this small set
_CANDIDATE_LIMIT = 50


def mask_email_heavily(email: str) -> str:
    """'frank.olaf@gmail.com' -> 'f*******@***.com'. Enough to tell two namesakes apart, not to contact them."""
    local, _, domain = (email or "").partition("@")
    if not local or not domain:
        return ""
    tld = domain.rsplit(".", 1)[-1] if "." in domain else ""
    stars = "*" * min(max(len(local) - 1, 1), 8)
    return f"{local[0]}{stars}@***" + (f".{tld}" if tld else "")


def _normalised_name(first_name: str, last_name: str) -> tuple[str, str]:
    return (first_name or "").strip().casefold(), (last_name or "").strip().casefold()


def _name_filter(tokens: list[str], prefix: str = "") -> Q:
    """Every token must appear in the first or the last name."""
    condition = Q()
    for token in tokens:
        condition &= Q(**{f"{prefix}first_name__icontains": token}) | Q(**{f"{prefix}last_name__icontains": token})
    return condition


def _rank(rows: list, tokens: list[str]) -> list:
    """Names that start with the typed text first, then alphabetical."""

    def starts_with_all(row) -> bool:
        first, last = _normalised_name(row.first_name, row.last_name)
        return all(first.startswith(token) or last.startswith(token) for token in tokens)

    return sorted(
        rows,
        key=lambda row: (not starts_with_all(row), *_normalised_name(row.last_name, row.first_name)),
    )


def _country_name(person: Optional[Person]) -> str:
    if person is None or not person.country:
        return ""
    return str(person.country.name)


def _to_results(rows: list, persons_by_email: dict[str, Person], reveal_hint: bool) -> list[dict]:
    """
    Builds the response. A masked email hint is attached only to rows whose name and country
    collide with another person in the whole database (not just within the returned page).
    """
    names = {_normalised_name(row.first_name, row.last_name) for row in rows}
    name_filter = Q()
    for first, last in names:
        name_filter |= Q(first_name__iexact=first, last_name__iexact=last)
    seen: Counter = Counter()
    if names:
        for person in Person.objects.filter(name_filter):
            seen[(*_normalised_name(person.first_name, person.last_name), _country_name(person))] += 1

    results = []
    for row in rows:
        person = persons_by_email.get(row.email.lower()) if not isinstance(row, Person) else row
        country = _country_name(person)
        key = (*_normalised_name(row.first_name, row.last_name), country)
        ambiguous = reveal_hint and seen[key] > 1
        name = f"{row.first_name} {row.last_name}".strip() or "(no name)"
        results.append(
            {
                "id": row.pk,
                "name": name,
                "country": country,
                "email_hint": mask_email_heavily(row.email) if ambiguous else "",
            }
        )
    return results


def _tokens(query: str) -> list[str]:
    return [token.casefold() for token in query.split() if token]


def search_persons(query: str, exclude_email: Optional[str] = None) -> list[dict]:
    query = (query or "").strip()
    if "@" in query:
        persons = list(Person.objects.filter(email__iexact=query)[:1])
        reveal_hint = False
    else:
        if len(query) < MIN_QUERY_LENGTH:
            return []
        tokens = _tokens(query)
        persons = list(
            Person.objects.filter(_name_filter(tokens)).order_by("last_name", "first_name")[:_CANDIDATE_LIMIT]
        )
        persons = _rank(persons, tokens)
        reveal_hint = True
    if exclude_email:
        persons = [person for person in persons if person.email.lower() != exclude_email.lower()]
    return _to_results(persons[:MAX_RESULTS], {}, reveal_hint)


def _persons_by_email(emails: Iterable[str]) -> dict[str, Person]:
    return {person.email.lower(): person for person in Person.objects.filter(email__in=list(emails))}


def search_users(query: str, exclude_user_id: Optional[int] = None) -> list[dict]:
    """Accounts only. A user whose own name is blank is still found through the matching Person's name."""
    query = (query or "").strip()
    if "@" in query:
        users = list(MyUser.objects.filter(email__iexact=query)[:1])
        reveal_hint = False
    else:
        if len(query) < MIN_QUERY_LENGTH:
            return []
        tokens = _tokens(query)
        person_emails = Person.objects.filter(_name_filter(tokens)).values_list("email", flat=True)
        users = list(
            MyUser.objects.filter(_name_filter(tokens) | Q(email__in=person_emails)).order_by(
                "last_name", "first_name"
            )[:_CANDIDATE_LIMIT]
        )
        reveal_hint = True
    persons = _persons_by_email(user.email for user in users)
    for user in users:
        # Fill in a blank account name from the Person record so it can be displayed and ranked
        person = persons.get(user.email.lower())
        if person and not (user.first_name or user.last_name):
            user.first_name, user.last_name = person.first_name, person.last_name
    if reveal_hint:
        users = _rank(users, _tokens(query))
    if exclude_user_id is not None:
        users = [user for user in users if user.pk != exclude_user_id]
    return _to_results(users[:MAX_RESULTS], persons, reveal_hint)
