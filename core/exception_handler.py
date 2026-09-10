from rest_framework.views import exception_handler


def api_errors(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        return None
    data = response.data
    if not isinstance(data, dict):
        return response
    if set(data.keys()) == {"error"}:
        return response
    if set(data.keys()) == {"detail"}:
        detail = data["detail"]
        if getattr(detail, "code", None) == "not_authenticated":
            text = "Authentication required."
        else:
            text = str(detail)
        response.data = {"error": text}
    else:
        flat = []
        for key, val in data.items():
            vals = val if isinstance(val, list) else [val]
            flat.append(f"{key}: {', '.join(str(v) for v in vals)}")
        response.data = {"error": "; ".join(flat)}
    return response
