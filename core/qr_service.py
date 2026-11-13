import json
import secrets
from datetime import timedelta
from queue import Empty, Queue

from django.http import StreamingHttpResponse
from django.db import transaction
from django.utils import timezone

from .models import AttendanceQrSession, SiteSetting

QR_TTL_SECONDS = 60
_SSE_SUBSCRIBERS = set()


def _payload_for_session(session):
    return {
        "token": session.token,
        "manual_code": session.manual_code,
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


def _create_active_qr_session():
    now = timezone.now()
    AttendanceQrSession.objects.filter(status=AttendanceQrSession.Status.ACTIVE).update(
        status=AttendanceQrSession.Status.EXPIRED,
        invalidated_at=now,
    )
    manual_code = f"{secrets.randbelow(1_000_000):06d}"
    while AttendanceQrSession.objects.filter(
        manual_code=manual_code,
        status=AttendanceQrSession.Status.ACTIVE,
        expires_at__gt=now,
    ).exists():
        manual_code = f"{secrets.randbelow(1_000_000):06d}"
    session = AttendanceQrSession.objects.create(
        token=secrets.token_urlsafe(32),
        manual_code=manual_code,
        expires_at=now + timedelta(seconds=QR_TTL_SECONDS),
        status=AttendanceQrSession.Status.ACTIVE,
    )
    payload = _payload_for_session(session)
    transaction.on_commit(lambda: broadcast_qr_event("qr_refresh", payload))
    return session


def create_active_qr_session():
    return get_active_qr_session(force_new=True)


def get_active_qr_session(force_new=False):
    # A stable row serializes generators even when no session exists yet.
    with transaction.atomic():
        lock_row, _ = SiteSetting.objects.get_or_create(
            key="_attendance_qr_lock", defaults={"value": "1"}
        )
        SiteSetting.objects.select_for_update().get(pk=lock_row.pk)
        now = timezone.now()
        session = (
            AttendanceQrSession.objects.filter(
                status=AttendanceQrSession.Status.ACTIVE,
                expires_at__gt=now,
            )
            .order_by("-created_at")
            .first()
        )
        if session is None or force_new or not session.manual_code:
            return _create_active_qr_session()
        return session


def invalidate_qr_session(session, *, used=False):
    if session is None:
        return None
    now = timezone.now()
    filters = {"pk": session.pk, "status": AttendanceQrSession.Status.ACTIVE}
    if used:
        filters["expires_at__gt"] = now
    updates = {
        "status": AttendanceQrSession.Status.USED if used else AttendanceQrSession.Status.EXPIRED,
        "invalidated_at": now,
    }
    if used:
        updates["used_at"] = now
    if not AttendanceQrSession.objects.filter(**filters).update(**updates):
        return None
    session.refresh_from_db()
    payload = _payload_for_session(session)
    transaction.on_commit(lambda: broadcast_qr_event("qr_refresh", payload))
    return session


def normalize_manual_code(value):
    normalized = "".join(str(value or "").upper().split())
    if normalized.startswith("K"):
        normalized = normalized[1:]
    if len(normalized) != 6 or not normalized.isascii() or not normalized.isdigit():
        return None
    return normalized


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
