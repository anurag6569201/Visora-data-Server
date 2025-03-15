# validators.py
from django.core.exceptions import ValidationError
import magic
import re

def validate_file_type(file):
    allowed_mime_types = {
        'text/html',
        'text/css',
        'application/javascript',
        'image/png',
        'image/jpeg'
    }
    
    file_mime_type = magic.from_buffer(file.read(1024), mime=True)
    file.seek(0)
    
    if file_mime_type not in allowed_mime_types:
        raise ValidationError(f"Unsupported file type: {file_mime_type}")

def sanitize_html(content):
    # Basic XSS protection
    cleaned = re.sub(r'<script\b[^>]*>(.*?)<\/script>', '', content, flags=re.IGNORECASE)
    return cleaned