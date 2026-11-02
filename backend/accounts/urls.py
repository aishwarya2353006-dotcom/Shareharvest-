from django.urls import path
from django.views.decorators.csrf import csrf_protect
from .views import UserViewSet, RegistrationViewSet, login_view, logout_view, csrf_token_view


def csrf_protected_login(request):
    # DRF API views are exempt from Django's middleware by default. Wrap the
    # public login endpoint outside that exemption to prevent login CSRF.
    return login_view(request)

urlpatterns = [
    path('register/', RegistrationViewSet.as_view({'post': 'create'}), name='register'),
    path('login/', csrf_protect(csrf_protected_login), name='login'),
    path('logout/', logout_view, name='logout'),
    path('csrf_token/', csrf_token_view, name='csrf_token'),
    path('me/', UserViewSet.as_view({'get': 'me', 'patch': 'me'}), name='me'),
    path('change-password/', UserViewSet.as_view({'post': 'change_password'}), name='change-password'),
]
