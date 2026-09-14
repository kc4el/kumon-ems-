import logging
import uuid
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django.shortcuts import render
from django.utils import timezone

from .models import (
    Department, Employee, Attendance, LeaveRequest, 
    ShiftRoster, PayrollRun, PayrollItem, PerformanceReview, EmployeeAuditLog
)
from .serializers import (
    DepartmentSerializer, EmployeeSerializer, AttendanceSerializer, 
    LeaveRequestSerializer, ShiftRosterSerializer, PayrollRunSerializer, 
    PayrollItemSerializer, PerformanceReviewSerializer, EmployeeAuditLogSerializer
)

from .supabase_client import supabase
from supabase_auth.errors import AuthApiError

logger = logging.getLogger(__name__)

def dashboard_view(request):
    return render(request, 'core/index.html')

class DashboardSummaryView(APIView):
    """Return the aggregate counts required by the dashboard landing page."""
    def get(self, request):
        try:
            total_employees = Employee.objects.count()
            active_employees = Employee.objects.filter(is_active=True).count()
            approved_leaves = LeaveRequest.objects.filter(status__iexact="approved").count()
            pending_leaves = LeaveRequest.objects.filter(status__iexact="pending").count()
            open_attendance = Attendance.objects.filter(clock_out__isnull=True).count()

            return Response({
                "total_employees": total_employees,
                "active_employees": active_employees,
                "approved_leaves": approved_leaves,
                "pending_leaves": pending_leaves,
                "open_attendance_records": open_attendance,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Dashboard summary error: {e}")
            return Response({"error": "Unable to load dashboard summary."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class DepartmentListCreateView(generics.ListCreateAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    pagination_class = None

class DepartmentDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer

class EmployeeListCreateView(generics.ListCreateAPIView):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer

    def post(self, request, *args, **kwargs):
        payload = request.data.copy()
        email = str(payload.get("email", "")).strip()
        
        if not email:
            return Response({"error": "An employee email address is required."}, status=status.HTTP_400_BAD_REQUEST)

        created_user_id = None
        try:
            record_id = str(uuid.uuid4())
            auth_response = supabase.auth.admin.create_user({
                "id": record_id,
                "email": email,
                "email_confirm": True,
                "user_metadata": {
                    "first_name": payload.get("first_name", ""),
                    "last_name": payload.get("last_name", ""),
                },
            })
            
            created_user_id = str(auth_response.user.id)
            payload["id"] = created_user_id
            payload["code"] = f"EMP-{created_user_id.replace('-', '')[:10].upper()}"

            serializer = self.get_serializer(data=payload)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as error:
            if created_user_id:
                try:
                    supabase.auth.admin.delete_user(created_user_id)
                except AuthApiError:
                    logger.exception(f"Unable to roll back Supabase Auth user {created_user_id}")
            
            logger.warning(f"Unable to create employee: {error}")
            return Response({"error": str(error)}, status=status.HTTP_502_BAD_GATEWAY)

class EmployeeDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer

class AttendanceListCreateView(generics.ListCreateAPIView):
    queryset = Attendance.objects.all().order_by('-date', '-clock_in')
    serializer_class = AttendanceSerializer

class AttendanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = Attendance.objects.all()
    serializer_class = AttendanceSerializer

class AttendanceClockOutView(APIView):
    def post(self, request):
        emp_id = request.data.get("employee_id")
        clock_out_time = request.data.get("clock_out") or timezone.now()

        try:
            attendance = Attendance.objects.get(employee_id=emp_id, clock_out__isnull=True)
            attendance.clock_out = clock_out_time
            attendance.save() 
            
            return Response({"message": "Clocked out successfully."}, status=status.HTTP_200_OK)
        except Attendance.DoesNotExist:
            return Response({"error": "No open clock-in found for this employee."}, status=status.HTTP_404_NOT_FOUND)


class LeaveRequestListCreateView(generics.ListCreateAPIView):
    queryset = LeaveRequest.objects.all().order_by('-created_at')
    serializer_class = LeaveRequestSerializer

class LeaveRequestDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = LeaveRequest.objects.all()
    serializer_class = LeaveRequestSerializer

class ShiftRosterListCreateView(generics.ListCreateAPIView):
    queryset = ShiftRoster.objects.all()
    serializer_class = ShiftRosterSerializer

class ShiftRosterDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ShiftRoster.objects.all()
    serializer_class = ShiftRosterSerializer

class PayrollRunListCreateView(generics.ListCreateAPIView):
    queryset = PayrollRun.objects.all()
    serializer_class = PayrollRunSerializer

class PayrollRunDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PayrollRun.objects.all()
    serializer_class = PayrollRunSerializer

class PayrollItemListCreateView(generics.ListCreateAPIView):
    queryset = PayrollItem.objects.all()
    serializer_class = PayrollItemSerializer

class PayrollItemDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PayrollItem.objects.all()
    serializer_class = PayrollItemSerializer

class PerformanceReviewListCreateView(generics.ListCreateAPIView):
    queryset = PerformanceReview.objects.all()
    serializer_class = PerformanceReviewSerializer

class PerformanceReviewDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PerformanceReview.objects.all()
    serializer_class = PerformanceReviewSerializer

class EmployeeAuditLogListView(generics.ListAPIView):
    queryset = EmployeeAuditLog.objects.all().order_by('-timestamp')
    serializer_class = EmployeeAuditLogSerializer
