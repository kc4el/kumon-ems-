"""Standalone stream lifecycle probe; does not import Django or the application."""
import ast
import json
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Lock
import unittest


class Response:
    def __init__(self, stream, content_type):
        self.stream = stream
        self.headers = {}

    def __setitem__(self, key, value):
        self.headers[key] = value

    def close(self):
        self.stream.close()


source = Path(__file__).resolve().parents[1] / "core" / "qr_service.py"
tree = ast.parse(source.read_text(encoding="utf-8"))
functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)
             and node.name in {"broadcast_qr_event", "stream_qr_events"}]
namespace = {"json": json, "Empty": Empty, "Full": Full, "Queue": Queue,
             "_SSE_SUBSCRIBERS": set(), "_SSE_LOCK": Lock(), "_SSE_QUEUE_SIZE": 32,
             "StreamingHttpResponse": Response}
exec(compile(ast.Module(body=functions, type_ignores=[]), str(source), "exec"), namespace)


class StreamTests(unittest.TestCase):
    def setUp(self):
        namespace["_SSE_SUBSCRIBERS"].clear()

    def test_close_before_and_after_iteration(self):
        response = namespace["stream_qr_events"](None)
        response.close()
        self.assertFalse(namespace["_SSE_SUBSCRIBERS"])
        response = namespace["stream_qr_events"](None)
        self.assertEqual(next(response.stream), "retry: 1000\n\n")
        self.assertEqual(len(namespace["_SSE_SUBSCRIBERS"]), 1)
        response.close()
        self.assertFalse(namespace["_SSE_SUBSCRIBERS"])

    def test_slow_client_is_bounded_and_other_client_receives(self):
        slow = namespace["stream_qr_events"](None)
        fast = namespace["stream_qr_events"](None)
        next(slow.stream); next(fast.stream)
        for value in range(100):
            namespace["broadcast_qr_event"]("qr_refresh", {"value": value})
            self.assertEqual(next(fast.stream), "event: qr_refresh\n")
            self.assertIn(f'"value": {value}', next(fast.stream))
        self.assertTrue(all(q.qsize() <= 32 for q in namespace["_SSE_SUBSCRIBERS"]))
        self.assertEqual(next(slow.stream), "event: qr_refresh\n")
        self.assertIn('"value": 68', next(slow.stream))
        slow.close(); fast.close()
        self.assertFalse(namespace["_SSE_SUBSCRIBERS"])


if __name__ == "__main__":
    unittest.main()
