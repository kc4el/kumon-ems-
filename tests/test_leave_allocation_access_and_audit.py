"""Entitlement access and audit provenance regressions (no external services)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from core.audit_context import AuditActorMiddleware, actor_name, current_actor
from core.models import Employee, EmployeeAuditLog, LeaveAllocation, LeaveRequest


class LeaveAllocationAccessTests(TestCase):
    def setUp(self):
        users = get_user_model()
        self.hr = users.objects.create_user('allocation-hr', is_staff=True)
        self.user = users.objects.create_user('allocation-employee')
        self.other_user = users.objects.create_user('allocation-other')
        self.employee = Employee.objects.create(first_name='Employee', last_name='One',
            email='allocation-one@example.test', user=self.user)
        self.other = Employee.objects.create(first_name='Employee', last_name='Two',
            email='allocation-two@example.test', user=self.other_user)
        self.allocation = LeaveAllocation.objects.create(employee=self.employee,
            leave_type='Vacation', year=2026, days_total=10)
        self.other_allocation = LeaveAllocation.objects.create(employee=self.other,
            leave_type='Vacation', year=2026, days_total=20)
        self.client = APIClient()

    def login(self, user):
        self.client.force_login(user)

    def detail(self, allocation=None):
        return f'/api/leave-allocations/{(allocation or self.allocation).pk}/'

    def test_employee_cannot_create_or_change_own_entitlement(self):
        self.login(self.user)
        self.assertEqual(self.client.post('/api/leave-allocations/', {
            'employee': str(self.employee.pk), 'leave_type': 'Sick', 'year': 2026,
            'days_total': 999}, format='json').status_code, 403)
        for method in ('patch', 'put', 'delete'):
            response = getattr(self.client, method)(self.detail(), {
                'employee': str(self.employee.pk), 'leave_type': 'Vacation',
                'year': 2026, 'days_total': 999}, format='json')
            self.assertEqual(response.status_code, 403, method)
        self.allocation.refresh_from_db()
        self.assertEqual(self.allocation.days_total, Decimal('10'))

    def test_employee_reads_only_own_allocations_and_balances(self):
        self.login(self.user)
        response = self.client.get('/api/leave-allocations/?year=2026')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['id'] for row in response.data['results']], [str(self.allocation.pk)])
        self.assertEqual(self.client.get(self.detail(self.other_allocation)).status_code, 404)
        self.assertEqual(self.client.get(f'/api/leave-balances/?employee={self.other.pk}&year=2026').status_code, 403)

    def test_hr_crud_and_duplicate_validation(self):
        self.login(self.hr)
        payload = {'employee':str(self.employee.pk), 'leave_type':'Study', 'year':2026, 'days_total':'0.0'}
        response = self.client.post('/api/leave-allocations/', payload, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        url = f"/api/leave-allocations/{response.data['id']}/"
        self.assertEqual(self.client.post('/api/leave-allocations/', payload, format='json').status_code, 409)
        self.assertEqual(self.client.patch(url, {'days_total':'7.5'}, format='json').status_code, 200)
        self.assertEqual(self.client.delete(url).status_code, 204)

    def test_balance_combines_defaults_overrides_and_custom_leave(self):
        LeaveAllocation.objects.create(employee=self.employee, leave_type='Study', year=2026, days_total=3)
        LeaveRequest.objects.create(employee=self.employee, leave_type='Vacation',
            start_date=date(2026, 1, 2), end_date=date(2026, 1, 3), reason='Test', status='Approved')
        self.login(self.user)
        response = self.client.get('/api/leave-balances/?year=2026')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data['balances']['Vacation'], {'allocated':10.0, 'used':2.0, 'remaining':8.0})
        self.assertEqual(response.data['balances']['Study']['allocated'], 3.0)
        self.assertIn('Sick', response.data['balances'])
        for value in ('0', '10000', 'invalid'):
            self.assertEqual(self.client.get('/api/leave-balances/?year=' + value).status_code, 400)
        self.login(self.hr)
        self.assertEqual(self.client.get('/api/leave-balances/?year=2026&employee=invalid').status_code, 400)

    def test_hr_mutation_records_actor_separately_from_employee(self):
        self.login(self.hr)
        response = self.client.patch(self.detail(), {'days_total':'11'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        log = EmployeeAuditLog.objects.get(action__startswith='Leave allocation updated:')
        self.assertEqual(log.actor_id, self.hr.pk)
        self.assertEqual(log.employee_id, self.employee.pk)
        self.assertEqual(log.actor_name, actor_name(self.hr))
        self.assertIsNone(current_actor())

    def test_token_authenticated_actor_is_captured(self):
        token = Token.objects.create(user=self.hr)
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + token.key)
        self.assertEqual(self.client.patch(self.detail(), {'days_total':'12'}, format='json').status_code, 200)
        log = EmployeeAuditLog.objects.get(action__startswith='Leave allocation updated:')
        self.assertEqual(log.actor_id, self.hr.pk)

    def test_actor_filter_is_not_affected_employee_filter(self):
        log = EmployeeAuditLog.objects.create(employee=self.employee, actor=self.hr, action='Actor filter regression')
        self.login(self.hr)
        response = self.client.get('/api/audit-logs/?actor_name=allocation-hr')
        self.assertIn(str(log.pk), [row['id'] for row in response.data['results']])
        response = self.client.get('/api/audit-logs/?actor_name=Employee%20One')
        self.assertNotIn(str(log.pk), [row['id'] for row in response.data['results']])
        self.hr.username = 'renamed-hr'
        self.hr.save()
        log.refresh_from_db()
        self.assertEqual(log.actor_name, 'allocation-hr')

    def test_legacy_actor_not_guessed_and_snapshot_survives_deletion(self):
        historical = EmployeeAuditLog.objects.create(employee=self.employee, action='Historical')
        EmployeeAuditLog.objects.filter(pk=historical.pk).update(actor_name='')
        explicit = EmployeeAuditLog.objects.create(employee=self.employee, actor=self.hr, action='Explicit')
        self.hr.delete()
        explicit.refresh_from_db()
        self.assertIsNone(explicit.actor_id)
        self.assertEqual(explicit.actor_name, 'allocation-hr')
        self.login(self.user)
        response = self.client.get('/api/audit-logs/?actor_name=Not%20recorded')
        self.assertEqual([row['id'] for row in response.data['results']], [str(historical.pk)])


class AuditContextIsolationTests(TestCase):
    def test_cleanup_on_exception_and_nested_requests(self):
        factory = RequestFactory()
        user = get_user_model().objects.create_user('context-actor')
        request = factory.get('/')
        request.user = user
        def fail(req):
            self.assertEqual(current_actor(), user)
            raise RuntimeError('failure')
        with self.assertRaises(RuntimeError):
            AuditActorMiddleware(fail)(request)
        self.assertIsNone(current_actor())
        response = AuditActorMiddleware(lambda req: HttpResponse('ok'))(request)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(current_actor())
