"""
URL configuration for config project.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('agents/', include('agents.urls')),
    path('tarifs/', include('tarifs.urls')),
    path('missions/', include('missions.urls')),
    path('gardes/', include('gardes.urls')),
    path('decomptes/', include('decomptes.urls')),
    path('paiements/', include('paiements.urls')),
    path('audit/', include('audit.urls')),
    path('', include('core.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
