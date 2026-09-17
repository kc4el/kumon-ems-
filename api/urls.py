from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from core.views import (
    AttendanceCheckInView,
    AttendanceClockOutView,
    AttendanceCorrectionDetailView,
    AttendanceCorrectionListCreateView,
    AttendanceDetailView,
    AttendanceListCreateView,
    AttendanceSelfView,
    ChangePasswordView,
    ClaimStatusListCreateView,
    ComplaintDetailView,
    ComplaintListCreateView,
    DashboardSummaryView,
    DepartmentDetailView,
    DepartmentListCreateView,
    EmployeeAuditLogListView,
    EmployeeDetailView,
    EmployeeListCreateView,
    ExpenseClaimDetailView,
    ExpenseClaimListCreateView,
    GrievanceDetailView,
    GrievanceListCreateView,
    HrSessionLoginView,
    LeaveAllocationDetailView,
    LeaveAllocationListCreateView,
    LeaveBalanceView,
    LeaveRequestDetailView,
    LeaveRequestListCreateView,
    MessageListCreateView,
    MySettingsView,
    NotificationListView,
    NotificationMarkReadView,
    OvertimeSlipDetailView,
    OvertimeSlipListCreateView,
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
    ShiftSwapDetailView,
    ShiftSwapListCreateView,
    SiteSettingsView,
)
from core.views_docs import (
    ClaimDecisionView,
    OnboardingDocumentListCreateView,
    SalaryAdvanceDetailView,
    SalaryAdvanceListCreateView,
)
from core.views_import import import_urls

urlpatterns = [
    path(
        "dashboard-summary/", DashboardSummaryView.as_view(), name="dashboard-summary"
    ),
    path("dashboard/", DashboardSummaryView.as_view(), name="dashboard-alias"),
    path("activities/", DashboardSummaryView.as_view(), name="activities-alias"),

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
    path(
        "complaints/", ComplaintListCreateView.as_view(), name="complaint-list-create"
    ),
    path(
        "complaints/<int:pk>/", ComplaintDetailView.as_view(), name="complaint-detail"
    ),
    path("employees/<uuid:pk>/", EmployeeDetailView.as_view(), name="employee-detail"),
    path(
        "grievances/", GrievanceListCreateView.as_view(), name="grievance-list-create"
    ),
    path(
        "grievances/<uuid:pk>/", GrievanceDetailView.as_view(), name="grievance-detail"
    ),
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
    path("attendance/me/", AttendanceSelfView.as_view(), name="attendance-self"),
    path(
        "attendance/check-in/",
        AttendanceCheckInView.as_view(),
        name="attendance-check-in",
    ),
    path("leaves/", LeaveRequestListCreateView.as_view(), name="leave-list-create"),
    path("leave-requests/", LeaveRequestListCreateView.as_view(), name="leave-requests-alias"),
    path("leaves/<uuid:pk>/", LeaveRequestDetailView.as_view(), name="leave-detail"),
    path(
        "leave-allocations/",
        LeaveAllocationListCreateView.as_view(),
        name="leave-allocation-list-create",
    ),
    path(
        "leave-allocations/<uuid:pk>/",
        LeaveAllocationDetailView.as_view(),
        name="leave-allocation-detail",
    ),
    path("leave-balances/", LeaveBalanceView.as_view(), name="leave-balances"),
    path(
        "overtime/", OvertimeSlipListCreateView.as_view(), name="overtime-list-create"
    ),
    path(
        "overtime/<uuid:pk>/",
        OvertimeSlipDetailView.as_view(),
        name="overtime-detail",
    ),
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
        "shift-swaps/",
        ShiftSwapListCreateView.as_view(),
        name="shift-swap-list-create",
    ),
    path(
        "shift-swaps/<uuid:pk>/",
        ShiftSwapDetailView.as_view(),
        name="shift-swap-detail",
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
    path("logs/", EmployeeAuditLogListView.as_view(), name="logs-alias"),
    path("auth-token/", obtain_auth_token, name="api-token"),
    path("session-login/", SessionLoginView.as_view(), name="session-login"),
    path("hr-session-login/", HrSessionLoginView.as_view(), name="hr-session-login"),
    path("session-logout/", SessionLogoutView.as_view(), name="session-logout"),
    path("settings/me/", MySettingsView.as_view(), name="settings-me"),
    path(
        "settings/password/",
        ChangePasswordView.as_view(),
        name="settings-password",
    ),
    path("settings/site/", SiteSettingsView.as_view(), name="settings-site"),
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
        "claims/",
        ExpenseClaimListCreateView.as_view(),
        name="claims-alias",
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
    path(
        "onboarding-docs/",
        OnboardingDocumentListCreateView.as_view(),
        name="onboarding-doc-list-create",
    ),
    path(
        "advances/",
        SalaryAdvanceListCreateView.as_view(),
        name="advance-list-create",
    ),
    path(
        "advances/<uuid:pk>/",
        SalaryAdvanceDetailView.as_view(),
        name="advance-detail",
    ),
    path(
        "claims/<str:pk>/decision/",
        ClaimDecisionView.as_view(),
        name="claim-decision",
    ),
]

urlpatterns += import_urls
