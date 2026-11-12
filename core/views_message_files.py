"""Authenticated downloads for message attachments."""
from pathlib import PurePosixPath
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView
from .models import Message


class MessageAttachmentDownloadView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        message = get_object_or_404(Message, pk=pk)
        # Keep access exactly aligned with the message endpoint.
        from .views import MessageListCreateView
        scope = MessageListCreateView()
        scope.request = request
        if not message.attachment or not scope._can_access_conversation(message.conversation_key):
            raise Http404
        try:
            file = message.attachment.open('rb')
        except (FileNotFoundError, OSError):
            raise Http404
        filename = PurePosixPath(message.attachment.name.replace('\\', '/')).name
        response = FileResponse(file, as_attachment=True, filename=filename, content_type='application/octet-stream')
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
