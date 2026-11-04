import hashlib

from rest_framework.throttling import SimpleRateThrottle


class MfaSessionThrottle(SimpleRateThrottle):
    """Rate-limit one-time-code guesses per pending login session."""

    scope = "mfa"

    def get_cache_key(self, request, view):
        ip = self.get_ident(request)
        pending_user_id = request.session.get("pending_mfa_user_id")
        payload = request.data if hasattr(request.data, "get") else {}
        username = str(payload.get("username", "")).strip().casefold()
        session_key = getattr(request.session, "session_key", None)
        authenticated_user = request.user.pk if getattr(request.user, "is_authenticated", False) else None
        identity = authenticated_user or pending_user_id or username or session_key
        if not identity:
            return None
        key_identity = hashlib.sha256(str(identity).encode("utf-8")).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{ip}:{key_identity}",
        }


class SessionLoginThrottle(MfaSessionThrottle):
    """Rate-limit password guesses per account and source IP."""

    scope = "login"


class EmployeeLoginThrottle(MfaSessionThrottle):
    """Rate-limit one-time employee credential attempts per ID and source IP."""

    scope = "onboarding_login"

    def get_cache_key(self, request, view):
        payload = request.data if hasattr(request.data, "get") else {}
        identifier = str(payload.get("employee_id", "")).strip().casefold()
        if not identifier:
            return super().get_cache_key(request, view)
        identity = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{self.get_ident(request)}:{identity}",
        }


class CredentialGenerationThrottle(MfaSessionThrottle):
    """Rate-limit HR credential issuance by operator and source IP."""

    scope = "onboarding_generate"

    def get_cache_key(self, request, view):
        user_id = getattr(getattr(request, "user", None), "pk", None)
        if not user_id:
            return super().get_cache_key(request, view)
        identity = hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()
        return self.cache_format % {
            "scope": self.scope,
            "ident": f"{self.get_ident(request)}:{identity}",
        }
