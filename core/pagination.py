from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_page_size(self, request):
        if self.page_size_query_param in request.query_params:
            return super().get_page_size(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            try:
                return user.setting.page_size
            except Exception:
                pass
        return self.page_size
