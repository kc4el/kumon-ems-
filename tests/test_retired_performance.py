from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import SimpleTestCase, TestCase


class RetiredPerformanceRoutesTests(SimpleTestCase):
    def test_review_routes_no_longer_resolve(self):
        for path in (
            "/api/performance/",
            "/api/performance/00000000-0000-0000-0000-000000000001/",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)


class RetiredPerformanceModelTests(TestCase):
    def test_model_is_absent_from_runtime_and_migration_state(self):
        with self.assertRaises(LookupError):
            apps.get_model("core", "PerformanceReview")

        state = MigrationExecutor(connection).loader.project_state()
        with self.assertRaises(LookupError):
            state.apps.get_model("core", "PerformanceReview")

    def test_legacy_table_is_preserved(self):
        self.assertIn("core_performancereview", connection.introspection.table_names())
