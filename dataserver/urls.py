from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import Http404
from landing import views as landing_views # Give it an alias if needed

urlpatterns = [
    # Use the dynamic prefix for the admin site
    path(f'{settings.ADMIN_URL_PREFIX}admin/', admin.site.urls),

    # Your existing app URLs
    path('', include('landing.urls')),
    path('', include('staticdata.urls')),
    path('', include('visoraai.urls')),
    path('', include('visoraplanner.urls')),
    path('auth/', include('dj_rest_auth.urls')),

    path('admin/', lambda request: Http404("Resource not found at this location")),
]

urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler404 = 'landing.views.page_not_found_view'
handler500 = 'landing.views.server_error_view'
handler403 = 'landing.views.permission_denied_view'
handler400 = 'landing.views.bad_request_view'
