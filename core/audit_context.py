"""Request-scoped audit identity, isolated between concurrent requests."""
from contextvars import ContextVar


audit_request = ContextVar("audit_request", default=None)


def current_actor():
    request = audit_request.get()
    # DRF also sets the underlying Django request's user after token auth.
    user = getattr(request, "user", None)
    return user if user is not None and user.is_authenticated else None


def actor_name(user):
    name = user.get_full_name().strip()
    username = user.get_username()
    return (f"{name} ({username})" if name and name != username else username)[:255]


class AuditActorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = audit_request.set(request)
        try:
            return self.get_response(request)
        finally:
            audit_request.reset(token)
