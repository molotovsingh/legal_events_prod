#!/usr/bin/env python3
"""
Generate Secure Credentials for Production Deployment

This script generates cryptographically secure random secrets for:
- JWT secret key
- PostgreSQL password
- MinIO root credentials
- MinIO access/secret keys

Usage:
    python3 scripts/generate_secrets.py

Output:
    Prints all generated secrets to stdout in .env format
    Copy and paste into your .env.production or .env.staging file
"""

import secrets
import string
import sys


def generate_jwt_secret(length: int = 64) -> str:
    """
    Generate a secure JWT secret key using URL-safe base64 encoding.

    Args:
        length: Number of random bytes (default 64 = 512 bits of entropy)

    Returns:
        URL-safe base64-encoded string
    """
    return secrets.token_urlsafe(length)


def generate_password(length: int = 32, alphanumeric_only: bool = False) -> str:
    """
    Generate a secure random password.

    Args:
        length: Password length (default 32 characters)
        alphanumeric_only: If True, use only letters and numbers (for compatibility)

    Returns:
        Random password string
    """
    if alphanumeric_only:
        # Some systems may not handle special characters well
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))
    else:
        # URL-safe encoding includes letters, numbers, - and _
        return secrets.token_urlsafe(length)


def generate_minio_username() -> str:
    """
    Generate a MinIO username with 'minio_' prefix.

    Returns:
        Username string like 'minio_a1b2c3d4e5f6g7h8'
    """
    return f"minio_{secrets.token_hex(8)}"


def print_separator(title: str = ""):
    """Print a section separator."""
    if title:
        print(f"\n# {'=' * 75}")
        print(f"# {title}")
        print(f"# {'=' * 75}\n")
    else:
        print(f"# {'-' * 75}\n")


def main():
    """Generate and print all secrets."""
    print("# =============================================================================")
    print("# GENERATED SECURE CREDENTIALS")
    print("# =============================================================================")
    print("#")
    print("# ⚠️  SECURITY WARNING:")
    print("#   - These are cryptographically secure random secrets")
    print("#   - Copy these values into your .env.production or .env.staging file")
    print("#   - NEVER commit these secrets to version control")
    print("#   - Store them securely (password manager, secrets vault, etc.)")
    print("#   - Generate new secrets for each environment (staging, production)")
    print("#")
    print("# Generated at:", end=" ")

    from datetime import datetime
    print(datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
    print("#")
    print("# =============================================================================\n")

    # JWT Secret
    print_separator("JWT Authentication")
    jwt_secret = generate_jwt_secret(64)
    print(f"JWT_SECRET_KEY={jwt_secret}")
    print(f"JWT_ALGORITHM=HS256")
    print(f"JWT_EXPIRY_HOURS=24")

    # PostgreSQL
    print_separator("PostgreSQL Database")
    postgres_password = generate_password(32)
    print(f"POSTGRES_PASSWORD={postgres_password}")
    print("#")
    print("# Note: You can also set custom values for:")
    print("# POSTGRES_DB=legal_events")
    print("# POSTGRES_USER=legal_user")

    # MinIO Root Credentials
    print_separator("MinIO Root Credentials (Admin Access)")
    minio_root_user = generate_minio_username()
    minio_root_password = generate_password(32)
    print(f"MINIO_ROOT_USER={minio_root_user}")
    print(f"MINIO_ROOT_PASSWORD={minio_root_password}")

    # MinIO Access Keys (Application Access)
    print_separator("MinIO Access Keys (Application Access)")
    minio_access_key = generate_password(32)
    minio_secret_key = generate_password(32)
    print(f"MINIO_ACCESS_KEY={minio_access_key}")
    print(f"MINIO_SECRET_KEY={minio_secret_key}")
    print("#")
    print("# Note: You can use the same values as ROOT credentials or separate ones")
    print("# Separate keys are recommended for better security (principle of least privilege)")

    # Additional Notes
    print_separator("Next Steps")
    print("# 1. Copy the values above into your .env file")
    print("# 2. Set your LLM provider API keys:")
    print("#    - Get keys from provider dashboards (see template comments)")
    print("#    - Add: GOOGLE_API_KEY=your-key-here")
    print("#    - Add: OPENROUTER_API_KEY=your-key-here")
    print("#    - Add: ANTHROPIC_API_KEY=your-key-here")
    print("#    etc.")
    print("#")
    print("# 3. Configure domain names:")
    print("#    - Set: MINIO_PUBLIC_ENDPOINT=storage.yourdomain.com")
    print("#    - Set: CORS_ORIGINS=https://app.yourdomain.com")
    print("#")
    print("# 4. Enable TLS (after setting up certificates):")
    print("#    - Set: MINIO_SECURE=true")
    print("#")
    print("# 5. Verify APP_ENV is set correctly:")
    print("#    - For production: APP_ENV=production")
    print("#    - For staging: APP_ENV=staging")
    print("#")
    print("# =============================================================================")
    print("# ENTROPY INFORMATION")
    print("# =============================================================================")
    print("#")
    print("# JWT Secret:         64 bytes = 512 bits of entropy")
    print("# PostgreSQL Password: 32 bytes = 256 bits of entropy")
    print("# MinIO Credentials:   32 bytes = 256 bits of entropy each")
    print("#")
    print("# These entropy levels exceed industry recommendations:")
    print("# - NIST recommends minimum 112 bits for cryptographic keys")
    print("# - OWASP recommends 128+ bits for secrets")
    print("#")
    print("# =============================================================================")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Generation cancelled by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\n\n❌ Error generating secrets: {e}", file=sys.stderr)
        sys.exit(1)
