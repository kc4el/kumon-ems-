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
