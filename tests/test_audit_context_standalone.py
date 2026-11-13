"""Run directly with Python; does not import Django or external services."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import runpy
from threading import Barrier
from types import SimpleNamespace
import unittest


audit = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'core' / 'audit_context.py'))
Middleware = audit['AuditActorMiddleware']
current_actor = audit['current_actor']


def user(name):
    return SimpleNamespace(is_authenticated=True, get_full_name=lambda: '', get_username=lambda: name)


class AuditContextTests(unittest.TestCase):
    def test_concurrent_requests_never_share_actors(self):
        barrier = Barrier(2)
        def run(name):
            actor = user(name)
            request = SimpleNamespace(user=actor)
            def view(req):
                barrier.wait(timeout=5)
                self.assertIs(current_actor(), actor)
                barrier.wait(timeout=5)
                return name
            self.assertEqual(Middleware(view)(request), name)
            self.assertIsNone(current_actor())
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = [executor.submit(run, name) for name in ('one', 'two')]
            for result in results:
                result.result(timeout=10)
        self.assertIsNone(current_actor())

    def test_nested_request_restores_outer_actor(self):
        outer, inner = user('outer'), user('inner')
        def view(req):
            self.assertIs(current_actor(), outer)
            Middleware(lambda req: self.assertIs(current_actor(), inner))(SimpleNamespace(user=inner))
            self.assertIs(current_actor(), outer)
        Middleware(view)(SimpleNamespace(user=outer))
        self.assertIsNone(current_actor())

    def test_exception_always_clears_context(self):
        def fail(req):
            raise RuntimeError('expected')
        with self.assertRaises(RuntimeError):
            Middleware(fail)(SimpleNamespace(user=user('actor')))
        self.assertIsNone(current_actor())

    def test_authentication_after_middleware_is_visible(self):
        actor = user('token-user')
        request = SimpleNamespace(user=SimpleNamespace(is_authenticated=False))
        def view(req):
            self.assertIsNone(current_actor())
            req.user = actor
            self.assertIs(current_actor(), actor)
        Middleware(view)(request)
        self.assertIsNone(current_actor())

    def test_actor_label_and_length(self):
        actor = user('hr')
        actor.get_full_name = lambda: 'HR Reviewer'
        self.assertEqual(audit['actor_name'](actor), 'HR Reviewer (hr)')
        actor.get_full_name = lambda: 'x' * 300
        self.assertEqual(len(audit['actor_name'](actor)), 255)


if __name__ == '__main__':
    unittest.main()
