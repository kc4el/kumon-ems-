"""Recipient-scoped invalidation events for the notification inbox."""
import hashlib
import time
from django.db import close_old_connections
from django.http import StreamingHttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .models import UserSetting
from .views_notifications import owned_notifications


def notification_cursor(user):
    setting = UserSetting.objects.filter(user=user).first()
    muted = setting.muted_kinds if setting and isinstance(setting.muted_kinds, list) else []
    rows = owned_notifications(user).exclude(kind__in=[x for x in muted if isinstance(x, str)])
    # Hash only identifiers and read state; event data contains no private text.
    state = '|'.join(f'{pk}:{int(read)}' for pk, read in rows.order_by('pk').values_list('pk', 'is_read'))
    return hashlib.sha256(state.encode()).hexdigest()


class NotificationEventsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        cursor = request.headers.get('Last-Event-ID', '')[:64]

        def events():
            nonlocal cursor
            try:
                for _ in range(15):
                    close_old_connections()
                    current = notification_cursor(user)
                    if current != cursor:
                        cursor = current
                        yield f'id: {current}\nevent: changed\ndata: {{}}\n\n'
                    else:
                        yield ': heartbeat\n\n'
                    time.sleep(2)
            finally:
                close_old_connections()

        response = StreamingHttpResponse(events(), content_type='text/event-stream')
        response['Cache-Control'] = 'private, no-cache, no-store'
        response['X-Accel-Buffering'] = 'no'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
