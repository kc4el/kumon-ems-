"""Front-end fix endpoints (D33/D36): onboarding docs, advances, claim decisions.

Models live here (instead of core/models.py) so this self-contained module can
be registered from CoreConfig.ready(); ``makemigrations core`` then picks up
the new tables without touching existing model files.
"""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import generics, serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClaimStatus, Employee, ExpenseClaim, SiteSetting
from .exceptions import Conflict409
from .permissions import (
    IsAuthenticatedReadOrStaffHRWrite,
    IsOwnerOrStaff,
    IsStaffOrHR,
    OwnerQuerysetMixin,
    is_staff_or_hr,
)

ONBOARDING_MAX_BYTES = 10 * 1024 * 1024
ONBOARDING_ALLOWED_TYPES = {
    "application/pdf": {"pdf"},
    "image/jpeg": {"jpg", "jpeg"},
    "image/png": {"png"},
}

DOC_TYPE_CHOICES = (
    ("NBI", "NBI Clearance"),
    ("BIR2316", "BIR Form 2316"),
    ("PSA", "PSA Birth Certificate"),
    ("contract", "Signed Employment Contract"),
    ("government_records", "Government Records"),
)

DECISION_CHOICES = ("Approved", "Rejected")

ADVANCE_STATUS_CHOICES = (
    ("Pending", "Pending"),
    ("Approved", "Approved"),
    ("Rejected", "Rejected"),
)


def _onboarding_max_bytes():
    """Onboarding upload cap from the onboarding_max_mb SiteSetting.

    Source of truth is SiteSetting (staff-editable); falls back to the
    ONBOARDING_MAX_BYTES default when unset, out of range, or on DB error.
    """
    try:
        raw = (
            SiteSetting.objects.filter(key="onboarding_max_mb")
            .values_list("value", flat=True)
            .first()
        )
        mb = float(raw) if raw not in (None, "") else 10
        if not 1 <= mb <= 100:
            return ONBOARDING_MAX_BYTES
        return int(mb * 1024 * 1024)
    except Exception:
        return ONBOARDING_MAX_BYTES


def validate_onboarding_file(upload):
    """Size (SiteSetting onboarding_max_mb) + MIME/extension guard."""
    cap = _onboarding_max_bytes()
    if upload.size > cap:
        raise ValidationError(
            f"File too large ({upload.size} bytes). Maximum is {cap} bytes."
        )
    content_type = getattr(upload, "content_type", "") or ""
    name = getattr(upload, "name", "") or ""
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    allowed_exts = ONBOARDING_ALLOWED_TYPES.get(content_type)
    if not allowed_exts or ext not in allowed_exts:
        raise ValidationError(
            "Unsupported file type. Allowed: PDF, JPG, PNG "
            f"(got {content_type or 'unknown'})."
        )


class OnboardingDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="onboarding_documents"
    )
    doc_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES)
    file = models.FileField(
        upload_to="onboarding-docs/%Y/%m/%d/",
        validators=[validate_onboarding_file],
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "core"
        ordering = ("-uploaded_at",)


class SalaryAdvance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="salary_advances"
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    repayment_terms = models.CharField(max_length=100, default="Next Payroll")
    purpose = models.TextField(blank=True)
    status = models.CharField(
        max_length=50, choices=ADVANCE_STATUS_CHOICES, default="Pending"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "core"
        ordering = ("-created_at",)


class OnboardingDocumentSerializer(serializers.ModelSerializer):
    file = serializers.FileField(validators=[validate_onboarding_file])

    class Meta:
        model = OnboardingDocument
        fields = ("id", "employee", "doc_type", "file", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data["file"] = reverse(
            "onboarding-doc-download", kwargs={"pk": instance.pk}
        )
        return data


class SalaryAdvanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryAdvance
        fields = (
            "id",
            "employee",
            "amount",
            "repayment_terms",
            "purpose",
            "status",
            "created_at",
        )
        read_only_fields = ("id", "status", "created_at")
        extra_kwargs = {"employee": {"required": False}}


class OnboardingDocumentListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
    queryset = OnboardingDocument.objects.all().order_by("-uploaded_at")
    serializer_class = OnboardingDocumentSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticatedReadOrStaffHRWrite]

    def get_queryset(self):
        queryset = super().get_queryset()
        employee_id = self.request.query_params.get("employee")
        if employee_id:
            employee_id = serializers.UUIDField().run_validation(employee_id)
            queryset = queryset.filter(employee_id=employee_id)
        return queryset


class OnboardingDocumentDetailView(
    OwnerQuerysetMixin, generics.RetrieveUpdateDestroyAPIView
):
    queryset = OnboardingDocument.objects.all()
    serializer_class = OnboardingDocumentSerializer
    parser_classes = (MultiPartParser, FormParser)
    permission_classes = [IsAuthenticatedReadOrStaffHRWrite]

    def perform_update(self, serializer):
        old_file = serializer.instance.file
        old_name = old_file.name
        storage = old_file.storage
        document = serializer.save()
        if old_name and old_name != document.file.name:
            transaction.on_commit(lambda: storage.delete(old_name))

    def perform_destroy(self, instance):
        file_name = instance.file.name
        storage = instance.file.storage
        instance.delete()
        if file_name:
            transaction.on_commit(lambda: storage.delete(file_name))


class OnboardingDocumentDownloadView(APIView):
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]

    def get(self, request, pk):
        document = get_object_or_404(OnboardingDocument, pk=pk)
        self.check_object_permissions(request, document)
        filename = document.file.name.rsplit("/", 1)[-1]
        response = FileResponse(
            document.file.open("rb"),
            as_attachment=True,
            filename=filename,
        )
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        return response


class SalaryAdvanceListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
    queryset = SalaryAdvance.objects.all().order_by("-created_at")
    serializer_class = SalaryAdvanceSerializer

    def perform_create(self, serializer):
        employee = Employee.objects.filter(user=self.request.user).first()
        selected_employee = serializer.validated_data.get("employee")
        if is_staff_or_hr(self.request.user):
            if selected_employee is None:
                if employee is None:
                    raise DRFValidationError(
                        {"employee": "Select an employee before submitting this request."}
                    )
                serializer.validated_data["employee"] = employee
        else:
            if employee is None:
                raise DRFValidationError({"employee": "No linked employee profile."})
            if selected_employee is not None and selected_employee.pk != employee.pk:
                raise DRFValidationError(
                    {"employee": "You can only submit an advance for your own profile."}
                )
            serializer.validated_data["employee"] = employee
        serializer.save()


class SalaryAdvanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SalaryAdvance.objects.all()
    serializer_class = SalaryAdvanceSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        self.queryset = self.queryset.select_for_update()
        instance = self.get_object()
        data = request.data
        if "employee" in data and str(data.get("employee")) != str(instance.employee_id):
            raise DRFValidationError({"employee": "The employee cannot be changed."})
        if "decision" in data or "status" in data:
            if not is_staff_or_hr(request.user):
                raise PermissionDenied("Only HR staff can decide salary advances.")
            if set(data.keys()) != {"decision"}:
                raise DRFValidationError({"decision": "Submit the decision separately from other changes."})
            decision = data.get("decision")
            if decision not in DECISION_CHOICES:
                raise DRFValidationError({"decision": "Must be Approved or Rejected."})
            if instance.status != "Pending" and instance.status != decision:
                raise Conflict409("This request has already been decided.")
            if instance.status == "Pending":
                instance.status = decision
                instance.save(update_fields=["status"])
            return Response(self.get_serializer(instance).data)
        if instance.status != "Pending":
            raise Conflict409("This request has already been decided.")
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        self.queryset = self.queryset.select_for_update()
        instance = self.get_object()
        if instance.status != "Pending":
            raise Conflict409("This request has already been decided.")
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClaimDecisionView(APIView):
    """POST /api/claims/<id>/decision/ {decision: Approved|Rejected}.

    UUIDs resolve to ExpenseClaim rows; any other id (e.g. demo CLM-/ADV-
    codes) is recorded via ClaimStatus upsert. Decisions are HR-only.
    """
    permission_classes = [IsStaffOrHR]

    def post(self, request, pk):
        decision = request.data.get("decision")
        if decision not in DECISION_CHOICES:
            return Response(
                {"error": "decision must be Approved or Rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        claim = ExpenseClaim.objects.filter(pk=pk).first() if _is_uuid(pk) else None
        if claim is not None:
            claim.status = decision
            claim.save(update_fields=["status"])
            ClaimStatus.objects.update_or_create(
                claim_id=str(claim.pk), defaults={"status": decision}
            )
            return Response(
                {"id": str(claim.pk), "status": claim.status},
                status=status.HTTP_200_OK,
            )
        obj, _ = ClaimStatus.objects.update_or_create(
            claim_id=str(pk), defaults={"status": decision}
        )
        return Response(
            {"claim_id": obj.claim_id, "status": obj.status},
            status=status.HTTP_200_OK,
        )


def _is_uuid(value):
    try:
        uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return False
    return True
