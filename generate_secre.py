import secrets

# Generate a secure random string
secret_key = secrets.token_hex(16)  # 16 bytes = 32 hex characters
print(f"Generated secret key: {secret_key}")