"""Front-end fix endpoints (D33/D36): onboarding docs, advances, claim decisions.

Models live here (instead of core/models.py) so this self-contained module can
be registered from CoreConfig.ready(); ``makemigrations core`` then picks up
the new tables without touching existing model files.
"""

import uuid
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from rest_framework import generics, serializers, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ClaimStatus, Employee, ExpenseClaim
from .permissions import IsOwnerOrStaff, OwnerQuerysetMixin, owns_object

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
)

DECISION_CHOICES = ("Approved", "Rejected")

ADVANCE_STATUS_CHOICES = (
    ("Pending", "Pending"),
    ("Approved", "Approved"),
    ("Rejected", "Rejected"),
)


def validate_onboarding_file(upload):
    """Size (10MB) + MIME/extension guard for onboarding documents."""
    if upload.size > ONBOARDING_MAX_BYTES:
        raise ValidationError(
            f"File too large ({upload.size} bytes). Maximum is "
            f"{ONBOARDING_MAX_BYTES} bytes."
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
    class Meta:
        model = OnboardingDocument
        fields = ("id", "employee", "doc_type", "file", "uploaded_at")
        read_only_fields = ("id", "uploaded_at")


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


class OnboardingDocumentListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
    queryset = OnboardingDocument.objects.all().order_by("-uploaded_at")
    serializer_class = OnboardingDocumentSerializer
    parser_classes = (MultiPartParser, FormParser)


class SalaryAdvanceListCreateView(OwnerQuerysetMixin, generics.ListCreateAPIView):
    queryset = SalaryAdvance.objects.all().order_by("-created_at")
    serializer_class = SalaryAdvanceSerializer


class SalaryAdvanceDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = SalaryAdvance.objects.all()
    serializer_class = SalaryAdvanceSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrStaff]

    def perform_update(self, serializer):
        decision = self.request.data.get("decision")
        if decision is not None:
            if decision not in DECISION_CHOICES:
                raise DRFValidationError({"decision": "Must be Approved or Rejected."})
            serializer.save(status=decision)
        else:
            serializer.save()


class ClaimDecisionView(APIView):
    """POST /api/claims/<id>/decision/ {decision: Approved|Rejected}.

    UUIDs resolve to ExpenseClaim rows (owner/staff guarded); any other id
    (e.g. demo CLM-/ADV- codes) is recorded via ClaimStatus upsert.
    """

    def post(self, request, pk):
        decision = request.data.get("decision")
        if decision not in DECISION_CHOICES:
            return Response(
                {"error": "decision must be Approved or Rejected."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        claim = ExpenseClaim.objects.filter(pk=pk).first() if _is_uuid(pk) else None
        if claim is not None:
            if not request.user.is_staff and not owns_object(claim, request.user):
                return Response(
                    {"error": "Not found."}, status=status.HTTP_404_NOT_FOUND
                )
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
