"""HR-only advisory estimates. These endpoints never authorize payment."""

import csv
import json
from collections.abc import Mapping
from decimal import Decimal

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.negotiation import DefaultContentNegotiation
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (Employee, EmployeeAuditLog, PayEstimate, PayEstimateAdjustment,
                     PayEstimatePolicy, PayEstimateRevision)
from .pay_estimates import create_revision, source_fingerprint
from .permissions import IsStaffOrHR


class EstimateAccessMixin:
    permission_classes = [IsAuthenticated, IsStaffOrHR]

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if not request.user.is_active or Employee.objects.filter(user=request.user, is_active=False).exists():
            raise PermissionDenied("An active account and employee profile are required.")


class StrictModelSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        if not isinstance(data, Mapping):
            return super().to_internal_value(data)
        extra = set(data) - {name for name, field in self.fields.items() if not field.read_only}
        if extra:
            raise ValidationError({key: "Unknown or read-only field." for key in extra})
        return super().to_internal_value(data)


class PolicySerializer(StrictModelSerializer):
    class Meta:
        model = PayEstimatePolicy
        fields = ("id", "effective_date", "overtime_threshold_hours", "overtime_multiplier", "paid_leave_types")
        read_only_fields = ("id",)

    def validate(self, attrs):
        threshold, multiplier = attrs.get("overtime_threshold_hours"), attrs.get("overtime_multiplier")
        if (threshold is None) != (multiplier is None):
            raise ValidationError("Overtime threshold and multiplier must both be provided or both omitted.")
        if threshold is not None and threshold < 0:
            raise ValidationError({"overtime_threshold_hours": "Must be nonnegative."})
        if multiplier is not None and multiplier < 1:
            raise ValidationError({"overtime_multiplier": "Must be at least 1."})
        types = attrs.get("paid_leave_types", [])
        if not isinstance(types, list) or any(not isinstance(t, str) or not t.strip() for t in types):
            raise ValidationError({"paid_leave_types": "Use a list of nonempty leave type names."})
        return attrs


class EstimateInputSerializer(StrictModelSerializer):
    class Meta:
        model = PayEstimate
        fields = ("employee", "period_start", "period_end", "hourly_rate", "deductions")

    def validate_employee(self, employee):
        if not employee.is_active:
            raise ValidationError("Employee must be active.")
        return employee

    def validate(self, attrs):
        instance = self.instance
        start = attrs.get("period_start", getattr(instance, "period_start", None))
        end = attrs.get("period_end", getattr(instance, "period_end", None))
        if start and end and start > end:
            raise ValidationError({"period_end": "Must not be before the start date."})
        for field in ("hourly_rate", "deductions"):
            value = attrs.get(field)
            if value is not None and value < 0:
                raise ValidationError({field: "Must be nonnegative."})
        return attrs


def audit(request, estimate, action, revision=None):
    number = revision.number if revision else "none"
    # Employee-facing audit feeds filter by employee; estimate activity is HR-only.
    EmployeeAuditLog.objects.create(employee=None, actor=request.user,
        action=f"Pay estimate {estimate.pk} revision {number}: {action} by user {request.user.pk}.")


def _decimal(value):
    return str(value) if value is not None else None


def _line(line):
    return {"id": str(line.pk), "work_date": line.work_date.isoformat(), "attendance": str(line.attendance_id) if line.attendance_id else None,
            "worked_seconds": _decimal(line.worked_seconds), "break_seconds": _decimal(line.break_seconds),
            "paid_seconds": _decimal(line.paid_seconds), "base_amount": _decimal(line.base_amount),
            "source": line.source}


def _adjustment(item):
    return {"id": str(item.pk), "kind": item.kind, "work_date": item.work_date.isoformat(),
            "hours": _decimal(item.hours), "hourly_rate": _decimal(item.hourly_rate),
            "multiplier": _decimal(item.multiplier), "amount": _decimal(item.amount),
            "status": item.status, "reviewed_by": item.reviewed_by_id,
            "reviewed_at": item.reviewed_at.isoformat() if item.reviewed_at else None,
            "reason": item.reason, "source_key": item.source_key}


def _revision(estimate, revision):
    if revision is None:
        return None
    stale = revision.number != estimate.current_revision or revision.fingerprint != source_fingerprint(estimate)
    items = list(revision.adjustments.all().order_by("work_date", "id"))
    lines = list(revision.lines.all().order_by("work_date", "id"))
    rounding = revision.base_amount - sum((line.base_amount for line in lines), Decimal("0.00"))
    approved = sum((item.amount for item in items if item.status == "Approved"), Decimal("0"))
    total = revision.base_amount + approved - revision.deductions
    return {"number": revision.number, "base_amount": _decimal(revision.base_amount),
            "deductions": _decimal(revision.deductions), "is_complete": revision.is_complete,
            "warnings": revision.warnings, "is_stale": stale,
            "lines": [_line(line) for line in lines],
            "rounding_reconciliation": _decimal(rounding),
            "adjustments": [_adjustment(item) for item in items],
            "approved_adjustments": _decimal(approved),
            "pending_adjustments": _decimal(sum((item.amount for item in items if item.status == "Pending"), Decimal("0"))),
            "approved_estimate": None if stale else _decimal(total), "snapshot_estimate": _decimal(total),
            "input_snapshot": revision.input_snapshot}


def _estimate(estimate, revision=None):
    revision = revision if revision is not None else estimate.revisions.filter(number=estimate.current_revision).first()
    current_inputs = {"employee": str(estimate.employee_id), "employee_name": str(estimate.employee),
                      "period_start": estimate.period_start.isoformat(), "period_end": estimate.period_end.isoformat(),
                      "hourly_rate": _decimal(estimate.hourly_rate), "deductions": _decimal(estimate.deductions)}
    header = current_inputs
    if revision and revision.number != estimate.current_revision:
        snapshot = revision.input_snapshot
        header = {"employee": snapshot["employee_id"], "employee_name": snapshot.get("employee_name", "Unknown"),
                  "period_start": snapshot["period_start"], "period_end": snapshot["period_end"],
                  "hourly_rate": snapshot["hourly_rate"], "deductions": snapshot["deductions"]}
    return {"id": str(estimate.pk), **header, "current_inputs": current_inputs,
            "current_revision": estimate.current_revision, "revision": _revision(estimate, revision)}


class PayEstimatePolicyListCreateView(EstimateAccessMixin, APIView):
    def get(self, request):
        return Response(PolicySerializer(PayEstimatePolicy.objects.all().order_by("-effective_date", "-created_at", "-id"), many=True).data)

    def post(self, request):
        serializer = PolicySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(created_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PayEstimateListCreateView(EstimateAccessMixin, APIView):
    def get(self, request):
        qs = PayEstimate.objects.select_related("employee").order_by("-period_end", "id")
        return Response([_estimate(estimate) for estimate in qs])

    def post(self, request):
        serializer = EstimateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            estimate = serializer.save(created_by=request.user)
            revision = create_revision(estimate, actor=request.user)
            estimate.refresh_from_db()
            audit(request, estimate, "created", revision)
        return Response(_estimate(estimate), status=status.HTTP_201_CREATED)


class PayEstimateDetailView(EstimateAccessMixin, APIView):
    def get(self, request, pk):
        estimate = get_object_or_404(PayEstimate.objects.select_related("employee"), pk=pk)
        return Response(_estimate(estimate))

    def patch(self, request, pk):
        with transaction.atomic():
            estimate = get_object_or_404(PayEstimate.objects.select_for_update(), pk=pk)
            serializer = EstimateInputSerializer(estimate, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            estimate = serializer.save()
            audit(request, estimate, "inputs updated", estimate.revisions.filter(number=estimate.current_revision).first())
        return Response(_estimate(estimate))


class PayEstimateRecalculateView(EstimateAccessMixin, APIView):
    def post(self, request, pk):
        with transaction.atomic():
            estimate = get_object_or_404(PayEstimate.objects.select_for_update(), pk=pk)
            revision = create_revision(estimate, actor=request.user)
            estimate.refresh_from_db()
            audit(request, estimate, "recalculated", revision)
        return Response(_estimate(estimate))


class PayEstimateRevisionView(EstimateAccessMixin, APIView):
    def get(self, request, pk, number):
        estimate = get_object_or_404(PayEstimate.objects.select_related("employee"), pk=pk)
        revision = get_object_or_404(PayEstimateRevision, estimate=estimate, number=number)
        return Response(_estimate(estimate, revision))


class PayEstimateAdjustmentDecisionView(EstimateAccessMixin, APIView):
    def post(self, request, pk):
        decision = request.data.get("status")
        reason = request.data.get("reason", "")
        if decision not in ("Approved", "Rejected"):
            raise ValidationError({"status": "Must be Approved or Rejected."})
        if not isinstance(reason, str):
            raise ValidationError({"reason": "Must be text."})
        if decision == "Rejected" and not reason.strip():
            raise ValidationError({"reason": "A rejection reason is required."})
        # Lock the parent first, in the same order as recalculation and input changes.
        candidate = get_object_or_404(PayEstimateAdjustment.objects.select_related("revision"), pk=pk)
        with transaction.atomic():
            estimate = get_object_or_404(PayEstimate.objects.select_for_update(), pk=candidate.revision.estimate_id)
            item = get_object_or_404(PayEstimateAdjustment.objects.select_for_update().select_related("revision"), pk=pk)
            revision = item.revision
            if revision.number != estimate.current_revision:
                return Response({"detail": "Only current revision adjustments can be decided."}, status=409)
            if revision.fingerprint != source_fingerprint(estimate):
                return Response({"detail": "Sources changed; recalculate before deciding."}, status=409)
            if item.status == decision:
                return Response(_adjustment(item))
            if item.status != "Pending":
                return Response({"detail": "This adjustment has already been decided."}, status=409)
            if decision == "Approved" and not revision.is_complete:
                return Response({"detail": "Resolve incomplete sources before approval."}, status=409)
            item.status, item.reason = decision, reason.strip()
            item.reviewed_by, item.reviewed_at = request.user, timezone.now()
            item.save(update_fields=["status", "reason", "reviewed_by", "reviewed_at"])
            audit(request, estimate, f"adjustment {item.pk} {decision}", revision)
        return Response(_adjustment(item))


class ExportNegotiation(DefaultContentNegotiation):
    def select_renderer(self, request, renderers, format_suffix=None):
        # The format query parameter selects the export, not a DRF renderer.
        return renderers[0], renderers[0].media_type


class PayEstimateExportView(EstimateAccessMixin, APIView):
    content_negotiation_class = ExportNegotiation

    def get(self, request, pk):
        estimate = get_object_or_404(PayEstimate.objects.select_related("employee"), pk=pk)
        payload = {"notice": "PAY ESTIMATE — FOR PAY-HANDLER REVIEW", "estimate": _estimate(estimate)}
        export_format = request.query_params.get("format", "json").lower()
        if export_format == "json":
            return Response(payload)
        if export_format != "csv":
            raise ValidationError({"format": "Choose csv or json."})
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="pay-estimate-{estimate.pk}.csv"'
        writer = csv.writer(response)
        def row(*values):
            # Protect spreadsheet users from formula execution in source text.
            writer.writerow(["'" + v if isinstance(v, str) and (v.startswith(("\t", "\r", "\n")) or v.lstrip().startswith(("=", "+", "-", "@"))) else v for v in values])
        row(payload["notice"])
        data = payload["estimate"]
        for key in ("employee_name", "period_start", "period_end", "hourly_rate", "deductions"):
            row(key, data[key])
        revision = data["revision"]
        if revision:
            for key in ("number", "is_complete", "is_stale", "warnings", "base_amount", "rounding_reconciliation", "deductions", "approved_adjustments", "pending_adjustments", "approved_estimate", "snapshot_estimate"):
                row(key, revision[key])
            row("SOURCE ROWS")
            for line in revision["lines"]:
                row("source", json.dumps(line, ensure_ascii=False))
            for section in ("attendance", "shifts", "leaves", "policies"):
                for source in revision["input_snapshot"].get(section, []):
                    row(section, json.dumps(source, ensure_ascii=False))
            row("ADJUSTMENTS")
            for item in revision["adjustments"]:
                row("adjustment", json.dumps(item, ensure_ascii=False))
        return response
