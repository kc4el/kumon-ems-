from tempfile import TemporaryDirectory
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient, APIRequestFactory, force_authenticate
from core.message_files import MAX_ATTACHMENT_SIZE, validate_message_attachment
from core.models import Employee, Message, Notification
from core.notification_events import NotificationEventsView, notification_cursor
from core.views_message_files import MessageAttachmentDownloadView


class MessageAttachmentTests(TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.settings = override_settings(MEDIA_ROOT=self.tmp.name)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        user = get_user_model()
        self.owner = user.objects.create_user(username='attachment_owner')
        self.other = user.objects.create_user(username='attachment_other')
        self.hr = user.objects.create_user(username='attachment_hr', is_staff=True)
        self.employee = Employee.objects.create(user=self.owner, first_name='Owner', last_name='One', email='owner@example.test')
        self.other_employee = Employee.objects.create(user=self.other, first_name='Other', last_name='Two', email='other@example.test')
        self.factory = APIRequestFactory()

    def request(self, view, user, pk=None, headers=None):
        request = self.factory.get('/api/', **(headers or {}))
        if user:
            force_authenticate(request, user)
        return view.as_view()(request, **({'pk': pk} if pk else {}))

    def test_upload_boundaries_and_content(self):
        for name, data in [('ok.txt', b'Hello\nworld'), ('ok.pdf', b'%PDF-1.4\n%%EOF')]:
            validate_message_attachment(SimpleUploadedFile(name, data))
        for name, data in [('fake.pdf', b'<script>x</script>'), ('bad.txt', b'<script>x</script>'), ('bad.svg', b'<svg/>'), ('empty.txt', b''), ('big.txt', b'x' * (MAX_ATTACHMENT_SIZE + 1))]:
            with self.subTest(name=name), self.assertRaises(ValidationError):
                validate_message_attachment(SimpleUploadedFile(name, data))

    def test_multipart_message_upload_and_download_route(self):
        client = APIClient()
        client.force_authenticate(self.owner)
        response = client.post('/api/messages/', {
            'conversation_key': f'hr_{self.employee.pk}', 'text': 'A caption',
            'attachment': SimpleUploadedFile('note.txt', b'hello'),
        }, format='multipart')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['text'], 'A caption')
        self.assertEqual(response.data['attachment_url'], f"/api/messages/{response.data['id']}/attachment/")
        download = client.get(response.data['attachment_url'])
        self.assertEqual(download.status_code, 200)
        self.assertEqual(b''.join(download.streaming_content), b'hello')
        download.close()
        client.force_authenticate(self.other)
        self.assertEqual(client.get(response.data['attachment_url']).status_code, 404)
        client.force_authenticate(self.owner)
        rejected = client.post('/api/messages/', {
            'conversation_key': f'hr_{self.employee.pk}',
            'attachment': SimpleUploadedFile('bad.txt', b'<script>x</script>'),
        }, format='multipart')
        self.assertEqual(rejected.status_code, 400)

        # Upload without text (file only)
        file_only = client.post('/api/messages/', {
            'conversation_key': f'hr_{self.employee.pk}',
            'text': '',
            'attachment': SimpleUploadedFile('only_file.txt', b'file only content'),
        }, format='multipart')
        self.assertEqual(file_only.status_code, 201, file_only.data)
        self.assertEqual(file_only.data['text'], '')
        self.assertEqual(file_only.data['attachment_name'], 'only_file.txt')
        self.assertTrue(file_only.data['attachment_url'])

        # Upload JPEG with trailing padding
        jpg_padded = b'\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00\xff\xd9\x00\x00'
        jpg_resp = client.post('/api/messages/', {
            'conversation_key': f'hr_{self.employee.pk}',
            'text': 'photo with padding',
            'attachment': SimpleUploadedFile('photo.jpg', jpg_padded, content_type='image/jpeg'),
        }, format='multipart')
        self.assertEqual(jpg_resp.status_code, 201, jpg_resp.data)
        self.assertEqual(jpg_resp.data['attachment_name'], 'photo.jpg')

    def test_private_download_and_headers(self):
        msg = Message.objects.create(conversation_key=f'hr_{self.employee.pk}', text='caption', attachment=SimpleUploadedFile('hello.txt', b'hello'))
        for user in (self.owner, self.hr):
            response = self.request(MessageAttachmentDownloadView, user, msg.pk)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b''.join(response.streaming_content), b'hello')
            self.assertIn('attachment;', response['Content-Disposition'])
            self.assertEqual(response['X-Content-Type-Options'], 'nosniff')
            self.assertIn('no-store', response['Cache-Control'])
            response.close()
        self.assertEqual(self.request(MessageAttachmentDownloadView, self.other, msg.pk).status_code, 404)
        self.assertIn(self.request(MessageAttachmentDownloadView, None, msg.pk).status_code, (401, 403))

    def test_stream_cursor_is_scoped_and_muted(self):
        before = notification_cursor(self.owner)
        Notification.objects.create(employee=self.other_employee, text='Private', kind='leave')
        self.assertEqual(before, notification_cursor(self.owner))
        self.owner.setting.muted_kinds = ['payroll']
        self.owner.setting.save(update_fields=['muted_kinds'])
        Notification.objects.create(employee=self.employee, text='Muted', kind='payroll')
        self.assertEqual(before, notification_cursor(self.owner))
        Notification.objects.create(employee=self.employee, text='Visible', kind='leave')
        self.assertNotEqual(before, notification_cursor(self.owner))
        response = self.request(NotificationEventsView, self.owner)
        event = next(iter(response.streaming_content)).decode()
        self.assertIn('event: changed', event)
        self.assertNotIn('Visible', event)
        self.assertEqual(response['Content-Type'], 'text/event-stream')
        response.close()
        self.assertIn(self.request(NotificationEventsView, None).status_code, (401, 403))
