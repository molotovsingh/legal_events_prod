#!/usr/bin/env python3
"""
Development password reset utility
Usage: python scripts/reset_dev_password.py <email> <new_password>
"""
import sys
import os
sys.path.insert(0, '.')

from infra.database import SessionLocal
from infra.models import User
from api.auth import get_password_hash


def reset_password(email: str, new_password: str):
    """Reset password for a user"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        if not user:
            print(f"❌ User not found: {email}")
            print("\nAvailable users:")
            all_users = db.query(User).all()
            for u in all_users:
                print(f"  - {u.email} ({u.role.value})")
            return False
        
        user.password_hash = get_password_hash(new_password)
        db.commit()
        print(f"✅ Password reset successful for {email}")
        print(f"   New password: {new_password}")
        return True
    except Exception as e:
        print(f"❌ Error resetting password: {e}")
        return False
    finally:
        db.close()


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/reset_dev_password.py <email> <new_password>")
        print("\nExample:")
        print("  python scripts/reset_dev_password.py dev@localhost newpassword123")
        sys.exit(1)
    
    email = sys.argv[1]
    password = sys.argv[2]
    
    if len(password) < 8:
        print("❌ Password must be at least 8 characters long")
        sys.exit(1)
    
    success = reset_password(email, password)
    sys.exit(0 if success else 1)
