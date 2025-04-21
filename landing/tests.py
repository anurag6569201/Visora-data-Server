import secrets
secret_path = secrets.token_urlsafe(32) # e.g., 32 bytes = 43 URL-safe characters
print(secret_path)
# Copy the output, e.g., 'kGjLpQx7v9zR3sYtWbNcVfMhZkPjTgUeD1aB8nOIo-_E'