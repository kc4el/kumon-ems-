from django.urls import path
from core.views import (
    DashboardSummaryView,
    DepartmentListCreateView,
    DepartmentDetailView,
    EmployeeListCreateView,
    EmployeeDetailView,
    AttendanceListCreateView,
    AttendanceDetailView,
    AttendanceClockOutView,
    LeaveRequestListCreateView,
    LeaveRequestDetailView,
    ShiftRosterListCreateView,
    ShiftRosterDetailView,
    PayrollRunListCreateView,
    PayrollRunDetailView,
    PayrollItemListCreateView,
    PayrollItemDetailView,
    PerformanceReviewListCreateView,
    PerformanceReviewDetailView,
    EmployeeAuditLogListView,
)

urlpatterns = [
    path('dashboard-summary/', DashboardSummaryView.as_view(), name='dashboard-summary'),

    path('departments/', DepartmentListCreateView.as_view(), name='department-list-create'),
    path('departments/<uuid:pk>/', DepartmentDetailView.as_view(), name='department-detail'),

    path('employees/', EmployeeListCreateView.as_view(), name='employee-list-create'),
    path('employees/<uuid:pk>/', EmployeeDetailView.as_view(), name='employee-detail'),

    path('attendance/', AttendanceListCreateView.as_view(), name='attendance-list-create'),
    path('attendance/<uuid:pk>/', AttendanceDetailView.as_view(), name='attendance-detail'),
    path('attendance/clock-out/', AttendanceClockOutView.as_view(), name='attendance-clock-out'),

    path('leaves/', LeaveRequestListCreateView.as_view(), name='leave-list-create'),
    path('leaves/<uuid:pk>/', LeaveRequestDetailView.as_view(), name='leave-detail'),

    path('shift-rosters/', ShiftRosterListCreateView.as_view(), name='shift-roster-list-create'),
    path('shift-rosters/<uuid:pk>/', ShiftRosterDetailView.as_view(), name='shift-roster-detail'),

    path('payroll-runs/', PayrollRunListCreateView.as_view(), name='payroll-run-list-create'),
    path('payroll-runs/<uuid:pk>/', PayrollRunDetailView.as_view(), name='payroll-run-detail'),

    path('payroll-items/', PayrollItemListCreateView.as_view(), name='payroll-item-list-create'),
    path('payroll-items/<uuid:pk>/', PayrollItemDetailView.as_view(), name='payroll-item-detail'),

    path('performance/', PerformanceReviewListCreateView.as_view(), name='performance-list-create'),
    path('performance/<uuid:pk>/', PerformanceReviewDetailView.as_view(), name='performance-detail'),

    path('audit-logs/', EmployeeAuditLogListView.as_view(), name='audit-log-list'),
]