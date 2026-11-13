"""Employee-owned claims and confidential HR case workflows."""

import uuid

from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Complaint, Employee, EmployeeAuditLog, ExpenseClaim, Grievance
from .notifications import notify_employee
from .permissions import is_staff_or_hr
from .serializers import ComplaintSerializer, ExpenseClaimSerializer, GrievanceSerializer


def active_employee(user):
    if not user.is_active:
        raise PermissionDenied("This account is inactive.")
    employee = Employee.objects.filter(user=user).first()
    if employee and not employee.is_active:
        raise PermissionDenied("This employee is inactive.")
    return employee


def audit(request, obj, action):
    EmployeeAuditLog.objects.create(
        employee=obj.employee,
        actor=request.user,
        action=f"{obj.__class__.__name__} {obj.pk}: {action} by user {request.user.pk}.",
    )


class CaseSerializerMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if not request or not is_staff_or_hr(request.user):
            self.fields.pop("internal_notes", None)
        self.fields["employee"].required = False
        if "source_complaint" in self.fields:
            self.fields["source_complaint"].read_only = True


class WorkflowComplaintSerializer(CaseSerializerMixin, ComplaintSerializer):
    pass


class WorkflowGrievanceSerializer(CaseSerializerMixin, GrievanceSerializer):
    pass


class WorkflowClaimSerializer(ExpenseClaimSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["employee"].required = False
        self.fields["status"].read_only = True


class WorkflowMixin:
    permission_classes = [IsAuthenticated]
    initial_status = None
    terminal = ()
    transitions = {}

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        self.actor_employee = active_employee(request.user)
        self.hr = is_staff_or_hr(request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.hr:
            qs = qs.filter(employee__user=self.request.user)
        selected = self.request.query_params.get("status", "")
        if selected:
            qs = qs.filter(status__in=[s.strip() for s in selected.split(",") if s.strip()])
        return qs

    def perform_create(self, serializer):
        data = self.request.data
        protected = {"resolution", "internal_notes", "source_complaint"}
        if protected.intersection(data):
            raise ValidationError("Workflow fields cannot be set at creation.")
        if "status" in data and data["status"] != self.initial_status:
            raise ValidationError({"status": "New items must use the initial status."})
        employee = self.actor_employee
        if self.hr and data.get("employee"):
            employee = get_object_or_404(Employee, pk=data["employee"], is_active=True)
        if not employee:
            raise PermissionDenied("An active employee profile is required.")
        with transaction.atomic():
            obj = serializer.save(employee=employee, status=self.initial_status)
            audit(self.request, obj, "created")

    def update(self, request, *args, **kwargs):
        with transaction.atomic():
            instance = get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=kwargs["pk"])
            data = request.data
            if "employee" in data and str(data["employee"]) != str(instance.employee_id):
                raise ValidationError({"employee": "Reassignment is not allowed."})
            if "source_complaint" in data:
                raise ValidationError({"source_complaint": "Use the escalation endpoint."})
            if not self.hr and {"status", "resolution", "internal_notes"}.intersection(data):
                raise PermissionDenied("Only HR can manage workflow fields.")
            new_status = data.get("status", instance.status)
            if isinstance(instance, ExpenseClaim) and "status" in data:
                raise ValidationError({"status": "Use the claim decision endpoint."})
            if instance.status in self.terminal:
                allowed = {"internal_notes"} if self.hr and not isinstance(instance, ExpenseClaim) else set()
                if set(data) - allowed:
                    raise ValidationError("This item has already been decided.")
            if not self.hr and instance.status != self.initial_status:
                raise PermissionDenied("This item is already under review.")
            if new_status != instance.status and new_status not in self.transitions.get(instance.status, ()):
                raise ValidationError({"status": "Invalid status transition."})
            if new_status in self.terminal and not isinstance(instance, ExpenseClaim):
                resolution = data.get("resolution", instance.resolution)
                if not isinstance(resolution, str) or not resolution.strip():
                    raise ValidationError({"resolution": "A resolution is required to close this case."})
            serializer = self.get_serializer(instance, data=data, partial=kwargs.get("partial", False))
            serializer.is_valid(raise_exception=True)
            old_status = instance.status
            obj = serializer.save(employee=instance.employee)
            audit(request, obj, "updated" if new_status == old_status else f"status changed to {new_status}")
            if new_status != old_status and obj.employee:
                notify_employee(obj.employee, f"Your {obj.__class__.__name__.lower()} has been {new_status}.",
                                "case", obj.__class__.__name__.lower(), obj.pk,
                                f"{obj.__class__.__name__.lower()}:{obj.pk}:{new_status}")
            return Response(serializer.data)

    def destroy(self, request, *args, **kwargs):
        with transaction.atomic():
            obj = get_object_or_404(self.get_queryset().select_for_update(of=("self",)), pk=kwargs["pk"])
            if obj.status != self.initial_status:
                raise ValidationError("Only items awaiting review can be deleted.")
            audit(request, obj, "deleted")
            obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExpenseClaimListCreateView(WorkflowMixin, generics.ListCreateAPIView):
    queryset = ExpenseClaim.objects.all().order_by("-created_at")
    serializer_class = WorkflowClaimSerializer
    initial_status = "Pending"


class ExpenseClaimDetailView(WorkflowMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = ExpenseClaim.objects.all()
    serializer_class = WorkflowClaimSerializer
    initial_status = "Pending"
    terminal = ("Approved", "Rejected")


class ComplaintListCreateView(WorkflowMixin, generics.ListCreateAPIView):
    queryset = Complaint.objects.select_related("employee").all().order_by("-created_at")
    serializer_class = WorkflowComplaintSerializer
    initial_status = "Open"


class ComplaintDetailView(WorkflowMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Complaint.objects.select_related("employee").all()
    serializer_class = WorkflowComplaintSerializer
    initial_status = "Open"
    terminal = ("Resolved", "Dismissed")
    transitions = {"Open": ("In Review",), "In Review": terminal}


class GrievanceListCreateView(WorkflowMixin, generics.ListCreateAPIView):
    queryset = Grievance.objects.select_related("employee", "employee__department").all()
    serializer_class = WorkflowGrievanceSerializer
    initial_status = "Pending"


class GrievanceDetailView(WorkflowMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = Grievance.objects.select_related("employee", "employee__department").all()
    serializer_class = WorkflowGrievanceSerializer
    initial_status = "Pending"
    terminal = ("Resolved", "Rejected")
    transitions = {"Pending": ("Investigating", "Resolved", "Rejected"),
                   "Investigating": ("In Mediation", "Resolved", "Rejected"),
                   "In Mediation": terminal}


class ClaimDecisionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        active_employee(request.user)
        if not is_staff_or_hr(request.user):
            raise PermissionDenied("Only HR can decide claims.")
        decision = request.data.get("status", request.data.get("decision"))
        if decision not in ("Approved", "Rejected") or (
            "status" in request.data and "decision" in request.data and request.data["status"] != request.data["decision"]
        ):
            raise ValidationError({"status": "Must be Approved or Rejected."})
        try:
            pk = uuid.UUID(str(pk))
        except (TypeError, ValueError, AttributeError):
            raise Http404
        with transaction.atomic():
            claim = get_object_or_404(ExpenseClaim.objects.select_for_update(), pk=pk)
            if claim.status == decision:
                return Response({"id": str(claim.pk), "status": claim.status})
            if claim.status != "Pending":
                return Response({"detail": "This claim has already been decided."}, status=409)
            claim.status = decision
            claim.save(update_fields=["status", "updated_at"])
            audit(request, claim, f"status changed to {decision}")
            notify_employee(claim.employee, f"Your expense claim has been {decision}.", "claim",
                            "claim", claim.pk, f"claim:{claim.pk}:{decision}")
        return Response({"id": str(claim.pk), "status": claim.status})


class ComplaintEscalateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        active_employee(request.user)
        if not is_staff_or_hr(request.user):
            raise PermissionDenied("Only HR can escalate complaints.")
        with transaction.atomic():
            complaint = get_object_or_404(Complaint.objects.select_for_update(), pk=pk)
            grievance, created = Grievance.objects.get_or_create(
                source_complaint=complaint,
                defaults={"employee": complaint.employee, "category": complaint.category,
                          "title": complaint.subject, "details": complaint.description},
            )
            if created:
                audit(request, grievance, "created by complaint escalation")
            return Response(WorkflowGrievanceSerializer(grievance, context={"request": request}).data,
                            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
