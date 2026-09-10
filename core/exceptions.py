from rest_framework.exceptions import APIException


class Conflict409(APIException):
    status_code = 409
    default_detail = "Conflict with existing data."
    default_code = "conflict"
