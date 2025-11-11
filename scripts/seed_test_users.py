#!/usr/bin/env python3
"""
Seed test users for development
Creates: admin, case_manager, and reviewer users
"""
import sys
import os
sys.path.insert(0, '.')

from infra.database import SessionLocal
from infra.models import User, UserRole
from api.auth import get_password_hash


TEST_USERS = [
    {
        "email": "admin@localhost",
        "name": "Admin User",
        "role": UserRole.ADMIN,
        "password": "admin123"
    },
    {
        "email": "manager@localhost",
        "name": "Case Manager",
        "role": UserRole.CASE_MANAGER,
        "password": "manager123"
    },
    {
        "email": "reviewer@localhost",
        "name": "Reviewer User",
        "role": UserRole.REVIEWER,
        "password": "reviewer123"
    },
    {
        "email": "dev@localhost",
        "name": "Development User",
        "role": UserRole.REVIEWER,
        "password": "devpass123"
    },
    {
        "email": "test@localhost",
        "name": "Test User",
        "role": UserRole.REVIEWER,
        "password": "test123"
    }
]


def seed_users():
    """Create test users if they don't exist"""
    db = SessionLocal()
    try:
        created = 0
        skipped = 0
        
        print("🌱 Seeding test users...")
        print("=" * 60)
        
        for user_data in TEST_USERS:
            existing = db.query(User).filter(User.email == user_data["email"]).first()
            if existing:
                print(f"⏭️  Skipped (already exists): {user_data['email']}")
                skipped += 1
                continue
            
            user = User(
                email=user_data["email"],
                name=user_data["name"],
                role=user_data["role"],
                password_hash=get_password_hash(user_data["password"]),
                is_active=True
            )
            db.add(user)
            created += 1
            print(f"✅ Created: {user_data['email']:<25} (password: {user_data['password']})")
        
        db.commit()
        
        print("=" * 60)
        print(f"📊 Summary: {created} created, {skipped} skipped, {created + skipped} total")
        
        # Print all users
        print("\n📋 All test users in database:")
        print("=" * 60)
        users = db.query(User).all()
        for user in users:
            # Find password if in test users
            pwd = "***"
            for test_user in TEST_USERS:
                if test_user["email"] == user.email:
                    pwd = test_user["password"]
                    break
            
            print(f"  {user.email:<30} | Role: {user.role.value:<15} | Password: {pwd}")
        
        print("=" * 60)
        print("\n✅ User seeding complete!")
        print("\nYou can now log in with any of the above credentials.")
        
    except Exception as e:
        print(f"❌ Error seeding users: {e}")
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed_users()
