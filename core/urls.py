from django.urls import path
from .views import (
    # 1. Departments
    DepartmentListCreateView,
    DepartmentDetailView,
    # 2. Employees
    EmployeeListCreateView,
    EmployeeDetailView,
    # 3. Attendance
    AttendanceListCreateView,
    AttendanceDetailView,
    AttendanceClockOutView,
    # 4. Leaves
    LeaveRequestListCreateView,
    LeaveRequestDetailView,
    # 5. Shift Rosters
    ShiftRosterListCreateView,
    ShiftRosterDetailView,
    # 6. Payroll Runs
    PayrollRunListCreateView,
    PayrollRunDetailView,
    # 7. Payroll Items
    PayrollItemListCreateView,
    PayrollItemDetailView,
    # 8. Performance Reviews
    PerformanceReviewListCreateView,
    PerformanceReviewDetailView,
    # 9. Audit Logs
    EmployeeAuditLogListView,
)

urlpatterns = [
    # Departments
    path('departments/', DepartmentListCreateView.as_view(), name='department-list-create'),
    path('departments/<uuid:pk>/', DepartmentDetailView.as_view(), name='department-detail'),

    # Employees
    path('employees/', EmployeeListCreateView.as_view(), name='employee-list-create'),
    path('employees/<uuid:pk>/', EmployeeDetailView.as_view(), name='employee-detail'),

    # Attendance
    path('attendance/', AttendanceListCreateView.as_view(), name='attendance-list-create'),
    path('attendance/<uuid:pk>/', AttendanceDetailView.as_view(), name='attendance-detail'),
    path('attendance/clock-out/', AttendanceClockOutView.as_view(), name='attendance-clock-out'),

    # Leaves
    path('leaves/', LeaveRequestListCreateView.as_view(), name='leave-list-create'),
    path('leaves/<uuid:pk>/', LeaveRequestDetailView.as_view(), name='leave-detail'),

    # Shift Rosters
    path('shift-rosters/', ShiftRosterListCreateView.as_view(), name='shift-roster-list-create'),
    path('shift-rosters/<uuid:pk>/', ShiftRosterDetailView.as_view(), name='shift-roster-detail'),

    # Payroll Runs
    path('payroll-runs/', PayrollRunListCreateView.as_view(), name='payroll-run-list-create'),
    path('payroll-runs/<uuid:pk>/', PayrollRunDetailView.as_view(), name='payroll-run-detail'),

    # Payroll Items
    path('payroll-items/', PayrollItemListCreateView.as_view(), name='payroll-item-list-create'),
    path('payroll-items/<uuid:pk>/', PayrollItemDetailView.as_view(), name='payroll-item-detail'),

    # Performance Reviews
    path('performance/', PerformanceReviewListCreateView.as_view(), name='performance-list-create'),
    path('performance/<uuid:pk>/', PerformanceReviewDetailView.as_view(), name='performance-detail'),

    # Audit Logs
    path('audit-logs/', EmployeeAuditLogListView.as_view(), name='audit-log-list'),
]