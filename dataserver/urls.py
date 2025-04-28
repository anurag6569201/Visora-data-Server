from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import Http404
from landing import views as landing_views

urlpatterns = [
    # Dynamic admin path
    path(f'{settings.ADMIN_URL_PREFIX}admin/', admin.site.urls),

    # App routes
    path('', include('landing.urls')),
    path('', include('staticdata.urls')),
    path('', include('visoraai.urls')),
    path('', include('visoraplanner.urls')),

    # Authentication routes
    path('auth/', include('dj_rest_auth.urls')),

    # Block direct /admin/ access
    path('admin/', lambda request: (_ for _ in ()).throw(Http404("Resource not found at this location"))),
]

# Static + Media
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Custom error handlers
handler400 = 'landing.views.bad_request_view'
handler403 = 'landing.views.permission_denied_view'
handler404 = 'landing.views.page_not_found_view'
handler500 = 'landing.views.server_error_view'
