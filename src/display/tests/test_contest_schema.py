"""The OpenAPI schema of the contest serialiser, which the apps' generated clients are built from."""

from django.test import TestCase
from drf_spectacular.generators import SchemaGenerator


class TestContestSchema(TestCase):
    def test_the_tasks_of_a_contest_are_a_list_of_tasks(self):
        schema = SchemaGenerator().get_schema(request=None, public=True)
        field = schema["components"]["schemas"]["ContestSerialiser"]["properties"]["navigationtask_set"]
        self.assertEqual(field.get("type"), "array", field)
