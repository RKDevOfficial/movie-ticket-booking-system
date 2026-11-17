from .models import Client


def profile_client(request):
    if not request.user.is_authenticated or not request.user.email:
        return {'profile_client': None}

    return {
        'profile_client': Client.objects.filter(
            email__iexact=request.user.email,
        ).first(),
    }
