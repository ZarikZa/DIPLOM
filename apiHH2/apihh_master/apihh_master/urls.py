
from django.contrib import admin
from django.urls import path
from django.urls import include
from rest_framework_simplejwt.views import (
    TokenRefreshView,
    TokenVerifyView,
)
from django.conf.urls.static import static
from django.conf import settings
from apihh_main.views import CustomTokenObtainPairView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('apihh_main.urls')), 
    path('api/token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('api/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('api/token/verify/', TokenVerifyView.as_view(), name='token_verify'),
]


if settings.DEBUG and not getattr(settings, 'USE_S3_MEDIA', False):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
