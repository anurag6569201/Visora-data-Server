# landing/views.py
from django.shortcuts import render
from django.conf import settings # Import settings
from django.http import HttpResponseNotFound, HttpResponseServerError, HttpResponseForbidden, HttpResponseBadRequest

def landing(request):
    """
    Render the landing page, passing the secret admin URL prefix.
    """
    context = {
        # Pass the secret segment (e.g., 'kGjLpQx7v9zR3sYtWbNcVfMhZkPjTgUeD1aB8nOIo-_E/')
        'admin_url_prefix': settings.ADMIN_URL_PREFIX
    }
    return render(request, 'landing/landing.html', context)

# --- Error Views ---

def page_not_found_view(request, exception):
    """
    Custom 404 Page Not Found view.
    """
    # You can optionally pass context if needed, but often it's simple
    # context = {'exception': exception} # Example if you want to show details (use with caution)
    return render(request, 'landing/404.html', status=404)
    # Alternatively, for a very basic response:
    # return HttpResponseNotFound("<h1>Page Not Found</h1><p>Sorry, the page you are looking for does not exist.</p>")

def server_error_view(request):
    """
    Custom 500 Internal Server Error view.
    """
    return render(request, 'landing/500.html', status=500)
    # Alternatively:
    # return HttpResponseServerError("<h1>Server Error</h1><p>Sorry, something went wrong on our end.</p>")

def permission_denied_view(request, exception):
    """
    Custom 403 Permission Denied view.
    """
    return render(request, 'landing/403.html', status=403)
    # Alternatively:
    # return HttpResponseForbidden("<h1>Permission Denied</h1><p>Sorry, you do not have permission to access this page.</p>")

def bad_request_view(request, exception):
    """
    Custom 400 Bad Request view.
    """
    return render(request, 'landing/400.html', status=400)
    # Alternatively:
    # return HttpResponseBadRequest("<h1>Bad Request</h1><p>Sorry, your request could not be understood by the server.</p>")