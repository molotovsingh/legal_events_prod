# Quick Start: Authentication & Login

## 🚀 For Users Having Login Issues

### Default Credentials (Development)
```
Email:    dev@localhost
Password: devpass123
```
**⚠️ Case-sensitive, no spaces!**

---

## 🛠️ Quick Fixes

### Option 1: Seed All Test Users
```bash
cd /Users/aks/legal-events-production
python scripts/seed_test_users.py
```

This creates:
- `admin@localhost` / `admin123` (Admin)
- `manager@localhost` / `manager123` (Case Manager)
- `reviewer@localhost` / `reviewer123` (Reviewer)
- `dev@localhost` / `devpass123` (Reviewer)
- `test@localhost` / `test123` (Reviewer)

### Option 2: Reset Password
```bash
python scripts/reset_dev_password.py dev@localhost devpass123
```

### Option 3: Reset via API
```bash
curl -X POST "http://localhost:8000/v1/auth/dev/reset-password?email=dev@localhost&new_password=devpass123"
```

---

## ✅ All Completed Tasks

1. ✅ **Database User Verification** - Confirmed dev@localhost exists
2. ✅ **Password Reset Mechanism** - Script + API endpoint
3. ✅ **Additional Test Users** - 5 users with different roles
4. ✅ **Improved Error Messages** - Helpful, actionable feedback
5. ✅ **Documentation** - Comprehensive user management guide

---

## 📚 Full Documentation
See `docs/USER_MANAGEMENT.md` for complete details.

## 📝 Summary
See `AUTH_IMPROVEMENTS_SUMMARY.md` for all changes made.
