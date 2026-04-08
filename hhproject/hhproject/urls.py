
from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from django.conf.urls.static import static
from home.metrics_view import prometheus_metrics_view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('home.urls')),
    path('compani/', include('compani.urls')),
    path('admin_panel/', include('admin_panel.urls')),
    path('prometheus/metrics', prometheus_metrics_view, name='prometheus-metric'),
        
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)