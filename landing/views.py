from django.shortcuts import render
from django.conf import settings

# Landing page view
def landing(request):
    context = {
        'admin_url_prefix': settings.ADMIN_URL_PREFIX
    }
    return render(request, 'landing/landing.html', context)

# Custom 404 error view (Page Not Found)
def page_not_found_view(request, exception):
    return render(request, 'landing/404.html', status=404)

# Custom 500 error view (Server Error)
def server_error_view(request):
    return render(request, 'landing/500.html', status=500)

# Custom 403 error view (Permission Denied)
def permission_denied_view(request, exception):
    return render(request, 'landing/403.html', status=403)

# Custom 400 error view (Bad Request)
def bad_request_view(request, exception):
    return render(request, 'landing/400.html', status=400)
