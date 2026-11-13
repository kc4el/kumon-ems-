"""Payroll endpoints with a single, atomic finalization boundary."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import generics, serializers, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .exceptions import Conflict409
from .models import PayrollItem, PayrollRun
from .permissions import IsStaffOrHR
from .serializers import PayrollItemSerializer, PayrollRunSerializer
from .signals import create_audit_log


def _audit(user, action):
    actor = getattr(user, "employee_profile", None)
    create_audit_log(actor, f"Payroll {action} by user {user.pk} ({user.get_username()}).", actor=user)


def _open(run):
    if run.is_processed:
        raise ValidationError({"payroll_run": "This pay run is already processed."})


def _amounts(base, deductions):
    if base is None or deductions is None:
        raise ValidationError("Both base pay and deductions are required.")
    if not base.is_finite() or base < 0:
        raise ValidationError({"base_pay": "Must be a nonnegative amount."})
    if not deductions.is_finite() or deductions < 0 or deductions > base:
        raise ValidationError({"deductions": "Must be between zero and base pay."})
    if base.as_tuple().exponent < -2 or deductions.as_tuple().exponent < -2:
        raise ValidationError("Amounts must have at most two decimal places.")
    return base - deductions


class PayrollRunListCreateView(generics.ListCreateAPIView):
    queryset = PayrollRun.objects.all().order_by("-pay_period_start")
    serializer_class = PayrollRunSerializer
    permission_classes = [IsAuthenticated, IsStaffOrHR]

    @transaction.atomic
    def perform_create(self, serializer):
        if serializer.validated_data.get("is_processed", False):
            raise ValidationError({"is_processed": "Use the finalize endpoint."})
        run = serializer.save(is_processed=False)
        _audit(self.request.user, f"run {run.pk} created")


class PayrollRunDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = PayrollRun.objects.all()
    serializer_class = PayrollRunSerializer
    permission_classes = [IsAuthenticated, IsStaffOrHR]

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        run = get_object_or_404(PayrollRun.objects.select_for_update(), pk=kwargs["pk"])
        self.check_object_permissions(request, run)
        _open(run)
        if "is_processed" in request.data:
            raise ValidationError({"is_processed": "Use the finalize endpoint."})
        serializer = self.get_serializer(run, data=request.data, partial=kwargs.pop("partial", False))
        serializer.is_valid(raise_exception=True)
        serializer.save()
        _audit(request.user, f"run {run.pk} updated")
        return Response(serializer.data)

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        run = get_object_or_404(PayrollRun.objects.select_for_update(), pk=kwargs["pk"])
        self.check_object_permissions(request, run)
        _open(run)
        _audit(request.user, f"run {run.pk} deleted")
        run.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PayrollItemScopeMixin:
    permission_classes = [IsAuthenticated, IsStaffOrHR]

    def get_queryset(self):
        queryset = super().get_queryset()
        run_id = self.request.query_params.get("payroll_run")
        if run_id:
            queryset = queryset.filter(payroll_run_id=serializers.UUIDField().run_validation(run_id))
        return queryset


class PayrollItemListCreateView(PayrollItemScopeMixin, generics.ListCreateAPIView):
    queryset = PayrollItem.objects.all().order_by("payroll_run__pay_period_start", "employee__last_name")
    serializer_class = PayrollItemSerializer

    def perform_create(self, serializer):
        try:
            with transaction.atomic():
                run = get_object_or_404(PayrollRun.objects.select_for_update(), pk=serializer.validated_data["payroll_run"].pk)
                _open(run)
                net = _amounts(serializer.validated_data["base_pay"], serializer.validated_data.get("deductions", Decimal("0.00")))
                item = serializer.save(payroll_run=run, net_pay=net)
                _audit(self.request.user, f"item {item.pk} created in run {run.pk}")
        except IntegrityError:
            raise Conflict409("Duplicate payroll line for this run and employee.")


class PayrollItemDetailView(PayrollItemScopeMixin, generics.RetrieveUpdateDestroyAPIView):
    queryset = PayrollItem.objects.all()
    serializer_class = PayrollItemSerializer

    def update(self, request, *args, **kwargs):
        try:
            with transaction.atomic():
                item = self.get_object()
                serializer = self.get_serializer(item, data=request.data, partial=kwargs.pop("partial", False))
                serializer.is_valid(raise_exception=True)
                new_run = serializer.validated_data.get("payroll_run", item.payroll_run)
                ids = sorted({item.payroll_run_id, new_run.pk}, key=str)
                runs = {r.pk: r for r in PayrollRun.objects.select_for_update().filter(pk__in=ids).order_by("pk")}
                item.refresh_from_db()
                if item.payroll_run_id not in runs or new_run.pk not in runs:
                    raise ValidationError("Payroll item changed concurrently; retry the request.")
                _open(runs[item.payroll_run_id])
                _open(runs[new_run.pk])
                # Revalidate against the current row after acquiring the run locks.
                serializer = self.get_serializer(item, data=request.data, partial=serializer.partial)
                serializer.is_valid(raise_exception=True)
                base = serializer.validated_data.get("base_pay", item.base_pay)
                deductions = serializer.validated_data.get("deductions", item.deductions)
                serializer.save(net_pay=_amounts(base, deductions))
                _audit(request.user, f"item {item.pk} updated in run {new_run.pk}")
                return Response(serializer.data)
        except IntegrityError:
            raise Conflict409("Duplicate payroll line for this run and employee.")

    @transaction.atomic
    def destroy(self, request, *args, **kwargs):
        item = self.get_object()
        run = get_object_or_404(PayrollRun.objects.select_for_update(), pk=item.payroll_run_id)
        item.refresh_from_db()
        if item.payroll_run_id != run.pk:
            raise ValidationError("Payroll item changed concurrently; retry the request.")
        _open(run)
        _audit(request.user, f"item {item.pk} deleted from run {run.pk}")
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PayrollFinalizeView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrHR]

    @transaction.atomic
    def post(self, request, pk):
        run = get_object_or_404(PayrollRun.objects.select_for_update(), pk=pk)
        if run.is_processed:
            return Response(PayrollRunSerializer(run).data)
        if run.pay_period_end < run.pay_period_start:
            raise ValidationError("pay_period_end must not precede pay_period_start.")
        items = list(PayrollItem.objects.filter(payroll_run=run).select_related("employee"))
        if not items:
            raise ValidationError("A payroll run must contain at least one item.")
        for item in items:
            item.net_pay = _amounts(item.base_pay, item.deductions)
            item.save(update_fields=["net_pay"])
        run.is_processed = True
        run.save(update_fields=["is_processed"])
        _audit(request.user, f"run {run.pk} finalized")
        return Response(PayrollRunSerializer(run).data)
