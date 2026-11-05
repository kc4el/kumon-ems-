import json
import secrets
from datetime import timedelta
from queue import Empty, Queue

from django.http import StreamingHttpResponse
from django.utils import timezone

from .models import AttendanceQrSession

QR_TTL_SECONDS = 60
_SSE_SUBSCRIBERS = set()


def _payload_for_session(session):
    return {
        "token": session.token,
        "status": session.status,
        "created_at": session.created_at.isoformat(),
        "expires_at": session.expires_at.isoformat(),
        "used_at": session.used_at.isoformat() if session.used_at else None,
        "invalidated_at": session.invalidated_at.isoformat() if session.invalidated_at else None,
    }


def broadcast_qr_event(event_name, payload):
    for subscriber in list(_SSE_SUBSCRIBERS):
        try:
            subscriber.put({"event": event_name, "payload": payload})
        except Exception:
            _SSE_SUBSCRIBERS.discard(subscriber)


def create_active_qr_session():
    now = timezone.now()
    AttendanceQrSession.objects.filter(status=AttendanceQrSession.Status.ACTIVE).update(
        status=AttendanceQrSession.Status.EXPIRED,
        invalidated_at=now,
    )
    session = AttendanceQrSession.objects.create(
        token=secrets.token_urlsafe(32),
        expires_at=now + timedelta(seconds=QR_TTL_SECONDS),
        status=AttendanceQrSession.Status.ACTIVE,
    )
    payload = _payload_for_session(session)
    broadcast_qr_event("qr_refresh", payload)
    return session


def get_active_qr_session(force_new=False):
    now = timezone.now()
    session = (
        AttendanceQrSession.objects.filter(
            status=AttendanceQrSession.Status.ACTIVE,
            expires_at__gt=now,
        )
        .order_by("-created_at")
        .first()
    )
    if session is None or force_new:
        return create_active_qr_session()
    return session


def invalidate_qr_session(session, *, used=False):
    if session is None:
        return None
    session.invalidate(used=used)
    payload = _payload_for_session(session)
    broadcast_qr_event("qr_refresh", payload)
    return session


def stream_qr_events(request):
    queue = Queue()
    _SSE_SUBSCRIBERS.add(queue)

    def event_stream():
        yield "retry: 1000\n\n"
        while True:
            try:
                message = queue.get(timeout=30)
            except Empty:
                yield ": heartbeat\n\n"
                continue
            yield f"event: {message['event']}\n"
            yield f"data: {json.dumps(message['payload'])}\n\n"

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response["Pragma"] = "no-cache"
    response["Expires"] = "0"
    response["X-Accel-Buffering"] = "no"
    return response
