"""
URL configuration for config project.
"""

from django.contrib import admin
from django.urls import include, path


urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('agents/', include('agents.urls')),
    path('tarifs/', include('tarifs.urls')),
    path('', include('core.urls')),
]
