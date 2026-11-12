"""Validation for private message attachments."""
from pathlib import PurePath
from rest_framework import serializers

MAX_ATTACHMENT_SIZE = 5 * 1024 * 1024


def validate_message_attachment(upload):
    if not upload or upload.size > MAX_ATTACHMENT_SIZE or upload.size == 0:
        raise serializers.ValidationError("Choose a nonempty file no larger than 5 MB.")
    name = upload.name.replace('\\', '/')
    ext = PurePath(name).suffix.lower()
    data = upload.read()
    upload.seek(0)
    valid = False
    if ext == '.pdf':
        valid = data.startswith(b'%PDF-') and b'%%EOF' in data[-1024:]
    elif ext in ('.jpg', '.jpeg'):
        valid = data.startswith(b'\xff\xd8\xff') and data.endswith(b'\xff\xd9')
    elif ext == '.png':
        valid = data.startswith(b'\x89PNG\r\n\x1a\n') and data.endswith(b'IEND\xaeB`\x82')
    elif ext == '.txt':
        try:
            decoded = data.decode('utf-8-sig')
            valid = all(ord(c) >= 32 or c in '\r\n\t' for c in decoded)
            # Do not serve active web content under a plain-text extension.
            lowered = decoded.lower()
            valid = valid and not any(token in lowered for token in ('<html', '<!doctype', '<script', '<svg', '<?xml'))
        except UnicodeDecodeError:
            pass
    if not valid:
        raise serializers.ValidationError("Use a valid PDF, JPEG, PNG, or UTF-8 text file.")
    return upload
