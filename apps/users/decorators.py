from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def role_required(*allowed_roles):
    def decorator(view_func):

        @wraps(view_func)
        def wrapper(request, *args, **kwargs):

            if not request.user.is_authenticated:
                return redirect("accounts:login")

            if request.user.profile_user.role not in allowed_roles:
                messages.error(
                    request,
                    "No tienes permisos para acceder a esta página."
                )
                return redirect("core:home")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator