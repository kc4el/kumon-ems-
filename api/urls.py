from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from core.views import (
    AttendanceClockOutView,
    AttendanceCorrectionDetailView,
    AttendanceCorrectionListCreateView,
    AttendanceDetailView,
    AttendanceListCreateView,
    ClaimStatusListCreateView,
    DashboardSummaryView,
    DepartmentDetailView,
    DepartmentListCreateView,
    EmployeeAuditLogListView,
    EmployeeDetailView,
    EmployeeListCreateView,
    ExpenseClaimDetailView,
    ExpenseClaimListCreateView,
    LeaveRequestDetailView,
    LeaveRequestListCreateView,
    MessageListCreateView,
    NotificationListView,
    NotificationMarkReadView,
    PayrollItemDetailView,
    PayrollItemListCreateView,
    PayrollRunDetailView,
    PayrollRunListCreateView,
    PerformanceReviewDetailView,
    PerformanceReviewListCreateView,
    PurgeRunView,
    SessionLoginView,
    SessionLogoutView,
    ShiftConflictView,
    ShiftRosterDetailView,
    ShiftRosterListCreateView,
)

urlpatterns = [
    path(
        "dashboard-summary/", DashboardSummaryView.as_view(), name="dashboard-summary"
    ),
    path(
        "departments/",
        DepartmentListCreateView.as_view(),
        name="department-list-create",
    ),
    path(
        "departments/<uuid:pk>/",
        DepartmentDetailView.as_view(),
        name="department-detail",
    ),
    path("employees/", EmployeeListCreateView.as_view(), name="employee-list-create"),
    path("employees/<uuid:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path(
        "attendance/", AttendanceListCreateView.as_view(), name="attendance-list-create"
    ),
    path(
        "attendance/<uuid:pk>/",
        AttendanceDetailView.as_view(),
        name="attendance-detail",
    ),
    path(
        "attendance-corrections/",
        AttendanceCorrectionListCreateView.as_view(),
        name="attendance-correction-list-create",
    ),
    path(
        "attendance-corrections/<uuid:pk>/",
        AttendanceCorrectionDetailView.as_view(),
        name="attendance-correction-detail",
    ),
    path(
        "attendance/clock-out/",
        AttendanceClockOutView.as_view(),
        name="attendance-clock-out",
    ),
    path("leaves/", LeaveRequestListCreateView.as_view(), name="leave-list-create"),
    path("leaves/<uuid:pk>/", LeaveRequestDetailView.as_view(), name="leave-detail"),
    path(
        "shift-rosters/",
        ShiftRosterListCreateView.as_view(),
        name="shift-roster-list-create",
    ),
    path(
        "shift-rosters/conflicts/",
        ShiftConflictView.as_view(),
        name="shift-conflicts",
    ),
    path(
        "shift-rosters/<uuid:pk>/",
        ShiftRosterDetailView.as_view(),
        name="shift-roster-detail",
    ),
    path(
        "payroll-runs/",
        PayrollRunListCreateView.as_view(),
        name="payroll-run-list-create",
    ),
    path(
        "payroll-runs/<uuid:pk>/",
        PayrollRunDetailView.as_view(),
        name="payroll-run-detail",
    ),
    path(
        "payroll-items/",
        PayrollItemListCreateView.as_view(),
        name="payroll-item-list-create",
    ),
    path(
        "payroll-items/<uuid:pk>/",
        PayrollItemDetailView.as_view(),
        name="payroll-item-detail",
    ),
    path(
        "performance/",
        PerformanceReviewListCreateView.as_view(),
        name="performance-list-create",
    ),
    path(
        "performance/<uuid:pk>/",
        PerformanceReviewDetailView.as_view(),
        name="performance-detail",
    ),
    path("audit-logs/", EmployeeAuditLogListView.as_view(), name="audit-log-list"),
    path("auth-token/", obtain_auth_token, name="api-token"),
    path("session-login/", SessionLoginView.as_view(), name="session-login"),
    path("session-logout/", SessionLogoutView.as_view(), name="session-logout"),
    path("messages/", MessageListCreateView.as_view(), name="message-list-create"),
    path(
        "claim-statuses/",
        ClaimStatusListCreateView.as_view(),
        name="claim-status-list-create",
    ),
    path(
        "expense-claims/",
        ExpenseClaimListCreateView.as_view(),
        name="expense-claim-list-create",
    ),
    path(
        "expense-claims/<uuid:pk>/",
        ExpenseClaimDetailView.as_view(),
        name="expense-claim-detail",
    ),
    path(
        "notifications/",
        NotificationListView.as_view(),
        name="notification-list",
    ),
    path(
        "notifications/<uuid:pk>/read/",
        NotificationMarkReadView.as_view(),
        name="notification-mark-read",
    ),
    path("purge-run/", PurgeRunView.as_view(), name="purge-run"),
]
