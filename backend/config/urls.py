from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('api/accounts/', include('accounts.urls')),
    path('api/organizations/', include('organizations.urls')),
    path('api/donations/', include('donations.urls')),
    path('api/donation-requests/', include('donation_requests.urls')),
    path('api/allocations/', include('donation_requests.allocation_urls')),
    path('api/pickups/', include('pickups.urls')),
    path('api/notifications/', include('notifications.urls')),
    path('api/impact/', include('impact.urls')),
    path('api/audit/', include('audit.urls')),
    path('api/compliance/', include('compliance.urls')),
]
