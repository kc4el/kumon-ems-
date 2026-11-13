import hmac
import logging
import secrets
from datetime import timedelta
from urllib.parse import urlencode

try:
    import requests
except ImportError:
    requests = None

from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

try:
    from google.auth.exceptions import GoogleAuthError
    from google.auth.transport.requests import Request as GoogleRequest
    from google.oauth2 import id_token
except ImportError:
    class GoogleAuthError(Exception):
        pass
    GoogleRequest = None
    id_token = None
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    AccountCredential,
    Department,
    Employee,
    EmployeeAuditLog,
    OAuthLink,
)
from .permissions import IsStaffOrHR, is_staff_or_hr
from .throttles import CredentialGenerationThrottle, EmployeeLoginThrottle

logger = logging.getLogger(__name__)

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
TEMP_PASSWORD_LIFETIME = timedelta(hours=24)
TEMP_PASSWORD_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
TEMP_PASSWORD_LENGTH = 12


def _employee_id_candidate():
    year = timezone.localdate().year
    for _ in range(50):
        candidate = f"EMP-{year}-{secrets.randbelow(9000) + 1000}"
        if not Employee.objects.filter(employee_id=candidate).exists() and not User.objects.filter(
            username=candidate
        ).exists():
            return candidate
    raise RuntimeError("Unable to allocate a unique employee ID.")


class OnboardEmployeeView(APIView):
    permission_classes = [IsAuthenticated, IsStaffOrHR]
    throttle_classes = [CredentialGenerationThrottle]

    def post(self, request):
        def text_field(name):
            value = request.data.get(name, "")
            return value.strip() if isinstance(value, str) else ""

        first_name = text_field("first_name")
        last_name = text_field("last_name")
        email = text_field("email")
        role = text_field("role")
        department_id = text_field("department")
        start_date_value = text_field("date_hired")
        start_date = parse_date(start_date_value) if start_date_value else timezone.localdate()
        if not first_name or not last_name or not email or start_date is None:
            return Response(
                {"error": "First name, last name, email, and a valid start date are required."},
                status=400,
            )
        if len(first_name) > 100 or len(last_name) > 100 or len(role) > 100:
            return Response(
                {"error": "Name fields and role must be 100 characters or fewer."},
                status=400,
            )
        if Employee.objects.filter(email__iexact=email).exists():
            return Response(
                {"error": "An employee with this email already exists."},
                status=409,
            )
        department = None
        if department_id:
            try:
                department = Department.objects.filter(pk=department_id).first()
            except ValidationError:
                department = None
            if department is None:
                return Response({"error": "Select a valid department."}, status=400)

        try:
            with transaction.atomic():
                employee_code = _employee_id_candidate()
                user = User(
                    username=employee_code,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    is_active=True,
                )
                user.set_unusable_password()
                user.save()
                employee = Employee(
                    employee_id=employee_code,
                    first_name=first_name,
                    last_name=last_name,
                    email=email,
                    role=role,
                    department=department,
                    date_hired=start_date,
                    is_active=True,
                    status=Employee.OnboardingStatus.PENDING_ONBOARDING,
                    force_password_change=True,
                    user=user,
                )
                employee.full_clean()
                employee.save()
                temporary_password = "".join(
                    secrets.choice(TEMP_PASSWORD_ALPHABET)
                    for _ in range(TEMP_PASSWORD_LENGTH)
                )
                AccountCredential.objects.create(
                    employee=employee,
                    password_hash=make_password(temporary_password, hasher="argon2"),
                    expires_at=timezone.now() + TEMP_PASSWORD_LIFETIME,
                )
                EmployeeAuditLog.objects.create(
                    employee=employee,
                    action=f"Onboarding credentials generated by HR user {request.user.pk}.",
                )

            response = Response(
                {
                    "employee_record_id": str(employee.pk),
                    "employee_name": f"{employee.first_name} {employee.last_name}",
                    "employee_id": employee.employee_id,
                    "temporary_password": temporary_password,
                    "expires_in_seconds": int(TEMP_PASSWORD_LIFETIME.total_seconds()),
                },
                status=201,
            )
            response["Cache-Control"] = "no-store, private"
            response["Pragma"] = "no-cache"
            return response
        except IntegrityError:
            logger.exception("Could not create employee onboarding record for %s", email)
            return Response(
                {"error": "Employee creation conflicted with an existing record. Check the email and retry."},
                status=409,
            )
        except ValidationError as exc:
            return Response({"error": exc.message_dict}, status=400)
        except RuntimeError:
            logger.exception("Employee ID allocation exhausted for new hire %s", email)
            return Response(
                {"error": "Unable to allocate an employee ID. Contact support."},
                status=503,
            )


@method_decorator(csrf_protect, name="dispatch")
class EmployeeCredentialLoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [EmployeeLoginThrottle]

    def post(self, request):
        employee_code = str(request.data.get("employee_id", "")).strip().upper()
        password = str(request.data.get("temporary_password", ""))
        with transaction.atomic():
            employee = (
                Employee.objects.select_for_update()
                .select_related("user")
                .filter(
                    employee_id=employee_code,
                    is_active=True,
                    status=Employee.OnboardingStatus.PENDING_ONBOARDING,
                    force_password_change=True,
                    user__isnull=False,
                )
                .first()
            )
            credential = (
                AccountCredential.objects.select_for_update()
                .filter(
                    employee=employee,
                    consumed_at__isnull=True,
                    expires_at__gt=timezone.now(),
                )
                .first()
                if employee
                else None
            )
            if (
                credential is None
                or not password
                or not employee.user.is_active
                or not check_password(password, credential.password_hash)
            ):
                return Response(
                    {"error": "Employee ID or temporary password is invalid."},
                    status=401,
                )

            user = employee.user
            user.set_password(password)
            user.save(update_fields=["password"])
            employee.status = Employee.OnboardingStatus.ACTIVE
            employee.force_password_change = False
            employee.save(update_fields=["status", "force_password_change"])
            EmployeeAuditLog.objects.create(
                employee=employee,
                action="Employee signed in with HR-issued credentials and activated the account.",
            )
            credential.delete()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            request.session.cycle_key()
            request.session.pop("onboarding_employee_id", None)
            request.session.set_expiry(None)

        response = Response(
            {"message": "Sign-in successful.", "next_url": "/employee/"}
        )
        response["Cache-Control"] = "no-store, private"
        return response


def _google_configuration():
    return bool(
        requests
        and id_token
        and settings.GOOGLE_OAUTH_CLIENT_ID
        and settings.GOOGLE_OAUTH_CLIENT_SECRET
    )


def _onboarding_employee(request):
    employee_id = request.session.get("onboarding_employee_id")
    if not request.user.is_authenticated or not employee_id:
        return None
    return Employee.objects.filter(
        pk=employee_id,
        user=request.user,
        is_active=True,
        status=Employee.OnboardingStatus.PENDING_ONBOARDING,
        force_password_change=True,
    ).first()


def _google_link_employee(request):
    if not request.user.is_authenticated or is_staff_or_hr(request.user):
        return None
    employee = Employee.objects.filter(
        user=request.user,
        is_active=True,
        status=Employee.OnboardingStatus.ACTIVE,
    ).first()
    return employee or _onboarding_employee(request)


class GoogleOAuthStartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        employee = _google_link_employee(request)
        if employee is None:
            return redirect("/employee/")
        if not _google_configuration():
            return JsonResponse(
                {"error": "Google OAuth is not configured. Contact the administrator."},
                status=503,
            )

        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        request.session["google_oauth_state"] = state
        request.session["google_oauth_nonce"] = nonce
        request.session["google_oauth_intent"] = "link"
        redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI or request.build_absolute_uri(
            reverse("google-oauth-callback")
        )
        params = {
            "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "nonce": nonce,
            "prompt": "select_account",
        }
        response = redirect(f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}")
        response["Cache-Control"] = "no-store"
        return response


@method_decorator(never_cache, name="dispatch")
class GoogleOAuthCallbackView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        expected_state = request.session.pop("google_oauth_state", "")
        expected_nonce = request.session.pop("google_oauth_nonce", "")
        intent = request.session.pop("google_oauth_intent", "")
        supplied_state = request.query_params.get("state", "")
        if (
            intent != "link"
            or not expected_state
            or not supplied_state
            or not hmac.compare_digest(expected_state, supplied_state)
        ):
            request.session.modified = True
            return HttpResponseBadRequest("Invalid or expired OAuth state.")
        employee = _google_link_employee(request)
        if employee is None:
            request.session.modified = True
            return HttpResponseBadRequest("Sign-in session expired. Sign in again to link your account.")
        if request.query_params.get("error"):
            request.session.modified = True
            return HttpResponseBadRequest("Google account linking was not completed.")
        code = request.query_params.get("code", "")
        if not code or not _google_configuration():
            request.session.modified = True
            return HttpResponseBadRequest("Invalid OAuth callback.")

        redirect_uri = settings.GOOGLE_OAUTH_REDIRECT_URI or request.build_absolute_uri(
            reverse("google-oauth-callback")
        )
        try:
            token_response = requests.post(
                GOOGLE_TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.GOOGLE_OAUTH_CLIENT_ID,
                    "client_secret": settings.GOOGLE_OAUTH_CLIENT_SECRET,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code",
                },
                timeout=10,
            )
            token_response.raise_for_status()
            response_data = token_response.json()
            id_token_value = (
                response_data.get("id_token")
                if isinstance(response_data, dict)
                else None
            )
            if not isinstance(id_token_value, str) or not id_token_value:
                return HttpResponseBadRequest("Google did not return an ID token.")
            claims = id_token.verify_oauth2_token(
                id_token_value,
                GoogleRequest(),
                settings.GOOGLE_OAUTH_CLIENT_ID,
            )
        except (requests.RequestException, ValueError, GoogleAuthError):
            logger.exception("Google OAuth verification failed for intent %s", intent)
            return HttpResponse("Google account verification failed. Please try linking again.", status=502)

        email = str(claims.get("email", "")).strip().lower()
        subject = str(claims.get("sub", "")).strip()
        allowed_domain = settings.GOOGLE_OAUTH_ALLOWED_DOMAIN
        if (
            not email
            or email.count("@") != 1
            or not subject
            or not hmac.compare_digest(str(claims.get("nonce", "")), expected_nonce)
            or claims.get("email_verified") is not True
            or (
                allowed_domain
                and email.rsplit("@", 1)[-1] != allowed_domain
            )
        ):
            return HttpResponseBadRequest("Google account does not meet the account-linking requirements.")

        try:
            with transaction.atomic():
                employee = Employee.objects.select_for_update().get(pk=employee.pk)
                existing = OAuthLink.objects.select_for_update().filter(
                    employee=employee, provider=OAuthLink.Provider.GOOGLE
                ).first()
                subject_owner = OAuthLink.objects.filter(
                    provider=OAuthLink.Provider.GOOGLE, subject=subject
                ).exclude(employee=employee).exists()
                if subject_owner or (existing and existing.subject != subject):
                    return HttpResponse(
                        "That Google account is already linked to another profile.",
                        status=409,
                    )
                OAuthLink.objects.update_or_create(
                    employee=employee,
                    defaults={
                        "provider": OAuthLink.Provider.GOOGLE,
                        "subject": subject,
                        "email": email,
                        "email_verified": True,
                    },
                )
                employee.status = Employee.OnboardingStatus.ACTIVE
                employee.force_password_change = False
                employee.save(update_fields=["status", "force_password_change"])
                EmployeeAuditLog.objects.create(
                    employee=employee,
                    action="Employee linked a verified Google account.",
                )
                AccountCredential.objects.filter(employee=employee).delete()
                request.user.email = email
                request.user.save(update_fields=["email"])
                Token.objects.filter(user=request.user).delete()
        except IntegrityError:
            logger.exception("Google account link conflict for employee %s", employee.pk)
            return HttpResponse("That Google account cannot be linked.", status=409)

        request.session.cycle_key()
        request.session.pop("onboarding_employee_id", None)
        request.session.pop("google_oauth_state", None)
        request.session.pop("google_oauth_nonce", None)
        request.session.set_expiry(None)
        login(request, request.user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("/employee/#settingsPanel")


@ensure_csrf_cookie
def hr_onboarding_view(request):
    if not request.user.is_authenticated:
        return redirect("/hr/login/?next=/hr/onboarding/")
    if not is_staff_or_hr(request.user):
        return HttpResponse("HR access required.", status=403)
    return render(
        request,
        "core/hr_onboarding.html",
        {
            "departments": Department.objects.order_by("name"),
            "today": timezone.localdate(),
        },
    )


@ensure_csrf_cookie
def onboarding_login_view(request):
    if request.user.is_authenticated:
        return redirect("/onboarding/" if _onboarding_employee(request) else "/employee/")
    return redirect("/login/")


@ensure_csrf_cookie
def onboarding_view(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    if _onboarding_employee(request) is None:
        return redirect("/employee/")
    return render(request, "core/onboarding.html")
