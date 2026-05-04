from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView, TokenVerifyView

from home.metrics_view import prometheus_metrics_view


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("api/token/verify/", TokenVerifyView.as_view(), name="token_verify"),
    path("api/", include("apihh_main.urls")),
    path("", include("home.urls")),
    path("compani/", include("compani.urls")),
    path("admin_panel/", include("admin_panel.urls")),
    path("prometheus/metrics", prometheus_metrics_view, name="prometheus-metric"),
]

if settings.DEBUG and not getattr(settings, "USE_S3_MEDIA", False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
