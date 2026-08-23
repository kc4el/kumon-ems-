from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import render
from .supabase_client import supabase
from postgrest.exceptions import APIError


# 0. Dashboard View
def dashboard_view(request):
    return render(request, 'core/index.html')


# 1. Departments
class DepartmentListCreateView(APIView):
    def get(self, request):
        try:
            result = supabase.table("departments").select("*").execute()
            return Response(result.data, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load departments."}, status=status.HTTP_502_BAD_GATEWAY)

    def post(self, request):
        try:
            result = supabase.table("departments").insert(request.data).execute()
            return Response(result.data, status=status.HTTP_201_CREATED)
        except APIError:
            return Response(
                {"error": "Unable to create department."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

class DepartmentDetailView(APIView):
    def get(self, request, pk):
        try:
            result = supabase.table("departments").select("*").eq("id", str(pk)).execute()
            return Response(result.data[0] if result.data else {}, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load department."}, status=status.HTTP_502_BAD_GATEWAY)

    def put(self, request, pk):
        try:
            result = supabase.table("departments").update(request.data).eq("id", str(pk)).execute()
            return Response(result.data, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to update department."}, status=status.HTTP_502_BAD_GATEWAY)

    def delete(self, request, pk):
        try:
            supabase.table("departments").delete().eq("id", str(pk)).execute()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except APIError:
            return Response({"error": "Unable to delete department."}, status=status.HTTP_502_BAD_GATEWAY)


# 2. Employees
class EmployeeListCreateView(APIView):
    def get(self, request):
        try:
            result = supabase.table("employees").select("*").execute()
            return Response(result.data, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load employees."}, status=status.HTTP_502_BAD_GATEWAY)

    def post(self, request):
        try:
            result = supabase.table("employees").insert(request.data).execute()
            return Response(result.data, status=status.HTTP_201_CREATED)
        except APIError:
            return Response(
                {"error": "Unable to create employee."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

class EmployeeDetailView(APIView):
    def get(self, request, pk):
        try:
            result = supabase.table("employees").select("*").eq("id", str(pk)).execute()
            return Response(result.data[0] if result.data else {}, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load employee."}, status=status.HTTP_502_BAD_GATEWAY)

    def put(self, request, pk):
        try:
            result = supabase.table("employees").update(request.data).eq("id", str(pk)).execute()
            return Response(result.data, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to update employee."}, status=status.HTTP_502_BAD_GATEWAY)

    def delete(self, request, pk):
        try:
            supabase.table("employees").delete().eq("id", str(pk)).execute()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except APIError:
            return Response({"error": "Unable to delete employee."}, status=status.HTTP_502_BAD_GATEWAY)


# 3. Attendance
class AttendanceListCreateView(APIView):
    def get(self, request):
        try:
            result = supabase.table("attendance").select("*").execute()
            return Response(result.data, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load attendance records."}, status=status.HTTP_502_BAD_GATEWAY)

    def post(self, request):
        try:
            result = supabase.table("attendance").insert(request.data).execute()
            return Response(result.data, status=status.HTTP_201_CREATED)
        except APIError:
            return Response(
                {"error": "Unable to create attendance record."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

class AttendanceDetailView(APIView):
    def get(self, request, pk):
        try:
            result = supabase.table("attendance").select("*").eq("id", str(pk)).execute()
            return Response(result.data[0] if result.data else {}, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load attendance record."}, status=status.HTTP_502_BAD_GATEWAY)

class AttendanceClockOutView(APIView):
    def post(self, request):
        try:
            emp_id = request.data.get("employee_id")
            clock_out_time = request.data.get("clock_out")
            result = supabase.table("attendance").update({"clock_out": clock_out_time}).eq("employee_id", emp_id).is_("clock_out", None).execute()
            return Response(result.data, status=status.HTTP_200_OK)
        except APIError:
            return Response(
                {"error": "Unable to clock out employee."},
                status=status.HTTP_502_BAD_GATEWAY,
            )


# 4. Leaves
class LeaveRequestListCreateView(APIView):
    def get(self, request):
        try:
            result = supabase.table("leave_requests").select("*").execute()
            return Response(result.data, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load leave requests."}, status=status.HTTP_502_BAD_GATEWAY)

    def post(self, request):
        try:
            result = supabase.table("leave_requests").insert(request.data).execute()
            return Response(result.data, status=status.HTTP_201_CREATED)
        except APIError:
            return Response(
                {"error": "Unable to submit leave request."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

class LeaveRequestDetailView(APIView):
    def get(self, request, pk):
        try:
            result = supabase.table("leave_requests").select("*").eq("id", str(pk)).execute()
            return Response(result.data[0] if result.data else {}, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load leave request."}, status=status.HTTP_502_BAD_GATEWAY)

    def put(self, request, pk):
        try:
            result = supabase.table("leave_requests").update(request.data).eq("id", str(pk)).execute()
            return Response(result.data, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to update leave request."}, status=status.HTTP_502_BAD_GATEWAY)


# 5. Shift Rosters
class ShiftRosterListCreateView(APIView):
    def get(self, request):
        try:
            result = supabase.table("shift_rosters").select("*").execute()
            return Response(result.data, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load shift rosters."}, status=status.HTTP_502_BAD_GATEWAY)

    def post(self, request):
        try:
            result = supabase.table("shift_rosters").insert(request.data).execute()
            return Response(result.data, status=status.HTTP_201_CREATED)
        except APIError:
            return Response(
                {"error": "Unable to create shift roster."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

class ShiftRosterDetailView(APIView):
    def get(self, request, pk):
        try:
            result = supabase.table("shift_rosters").select("*").eq("id", str(pk)).execute()
            return Response(result.data[0] if result.data else {}, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load shift roster."}, status=status.HTTP_502_BAD_GATEWAY)


# 6. Payroll Runs
class PayrollRunListCreateView(APIView):
    def get(self, request):
        try:
            result = supabase.table("payroll_runs").select("*").execute()
            return Response(result.data, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load payroll runs."}, status=status.HTTP_502_BAD_GATEWAY)

    def post(self, request):
        try:
            result = supabase.table("payroll_runs").insert(request.data).execute()
            return Response(result.data, status=status.HTTP_201_CREATED)
        except APIError:
            return Response(
                {"error": "Unable to create payroll run."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

class PayrollRunDetailView(APIView):
    def get(self, request, pk):
        try:
            result = supabase.table("payroll_runs").select("*").eq("id", str(pk)).execute()
            return Response(result.data[0] if result.data else {}, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load payroll run."}, status=status.HTTP_502_BAD_GATEWAY)


# 7. Payroll Items
class PayrollItemListCreateView(APIView):
    def get(self, request):
        try:
            result = supabase.table("payroll_items").select("*").execute()
            return Response(result.data, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load payroll items."}, status=status.HTTP_502_BAD_GATEWAY)

    def post(self, request):
        try:
            result = supabase.table("payroll_items").insert(request.data).execute()
            return Response(result.data, status=status.HTTP_201_CREATED)
        except APIError:
            return Response(
                {"error": "Unable to create payroll item."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

class PayrollItemDetailView(APIView):
    def get(self, request, pk):
        try:
            result = supabase.table("payroll_items").select("*").eq("id", str(pk)).execute()
            return Response(result.data[0] if result.data else {}, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load payroll item."}, status=status.HTTP_502_BAD_GATEWAY)


# 8. Performance Reviews
class PerformanceReviewListCreateView(APIView):
    def get(self, request):
        try:
            result = supabase.table("core_performancereview").select("*").execute()
            return Response(result.data, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load performance reviews."}, status=status.HTTP_502_BAD_GATEWAY)

    def post(self, request):
        try:
            result = supabase.table("core_performancereview").insert(request.data).execute()
            return Response(result.data, status=status.HTTP_201_CREATED)
        except APIError:
            return Response(
                {"error": "Unable to create performance review."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

class PerformanceReviewDetailView(APIView):
    def get(self, request, pk):
        try:
            result = supabase.table("core_performancereview").select("*").eq("id", str(pk)).execute()
            return Response(result.data[0] if result.data else {}, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load performance review."}, status=status.HTTP_502_BAD_GATEWAY)


# 9. Audit Logs
class EmployeeAuditLogListView(APIView):
    def get(self, request):
        try:
            result = supabase.table("employee_audit_logs").select("*").execute()
            return Response(result.data, status=status.HTTP_200_OK)
        except APIError:
            return Response({"error": "Unable to load audit logs."}, status=status.HTTP_502_BAD_GATEWAY)

