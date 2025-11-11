# User Management Guide

## Overview
This guide covers user authentication, password management, and troubleshooting for the Legal Events Extraction system.

## Development Users

### Default Credentials
The system automatically creates a development user on first startup:

- **Email:** dev@localhost
- **Password:** devpass123
- **Role:** Reviewer
- **Status:** Active

### Security Note
⚠️ **The default development credentials are for local development only.** In production/staging environments, you must configure proper admin credentials via environment variables.

## Managing Users

### 1. Seed Test Users (Development)
Create a full set of test users for all roles:

```bash
python scripts/seed_test_users.py
```

This creates the following users:

| Email                | Password    | Role          | Purpose                    |
|----------------------|-------------|---------------|----------------------------|
| admin@localhost      | admin123    | Admin         | Full system access         |
| manager@localhost    | manager123  | Case Manager  | Manage cases & assignments |
| reviewer@localhost   | reviewer123 | Reviewer      | Review & extract events    |
| dev@localhost        | devpass123  | Reviewer      | Default development user   |
| test@localhost       | test123     | Reviewer      | Testing purposes           |

### 2. Reset User Password (Development)
If you forget a password or need to reset it:

```bash
python scripts/reset_dev_password.py <email> <new_password>
```

**Examples:**
```bash
# Reset dev user password
python scripts/reset_dev_password.py dev@localhost mynewpassword

# Reset admin password
python scripts/reset_dev_password.py admin@localhost newsecurepass123
```

### 3. API Password Reset (Development Only)
You can also reset passwords via the API endpoint:

```bash
curl -X POST "http://localhost:8000/v1/auth/dev/reset-password?email=dev@localhost&new_password=newpass123"
```

**Security:** This endpoint is automatically disabled in production and staging environments.

## Production Setup

### Configure Admin Credentials
Set these environment variables **before** starting the application:

```bash
# Generate a secure password hash
export ADMIN_PASSWORD_HASH=$(python -c "import bcrypt; print(bcrypt.hashpw(b'your-secure-password', bcrypt.gensalt()).decode())")

# Set admin email and hash
export ADMIN_EMAIL="admin@company.com"
export ADMIN_NAME="System Administrator"

# Set environment mode (disables dev endpoints)
export ENVIRONMENT="production"
```

### Generate Secure Password Hash
```bash
python -c "import bcrypt; print(bcrypt.hashpw(b'your-secure-password', bcrypt.gensalt()).decode())"
```

### Verify Configuration
Check that admin credentials are set:

```bash
echo $ADMIN_EMAIL
echo $ADMIN_PASSWORD_HASH  # Should be a bcrypt hash (starts with $2b$)
```

## Login Process

### Web UI Login
1. Open the application in your browser
2. Click the **Login** button (or you'll see the login modal automatically)
3. Enter your credentials:
   - Email: `dev@localhost` (or your user email)
   - Password: `devpass123` (or your password)
4. Click **Login**

### API Login
Use the `/v1/auth/login` endpoint:

```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"dev@localhost","password":"devpass123"}'
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "user": {
    "email": "dev@localhost",
    "name": "Development User",
    "role": "reviewer"
  }
}
```

### Use the Token
Include the token in subsequent API requests:

```bash
curl -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  http://localhost:8000/v1/clients
```

## User Roles

### Admin
- Full system access
- Can create/manage users
- Can manage all clients and cases
- Can access all runs and data

### Case Manager
- Create and manage clients
- Create and manage cases
- Assign users to cases
- Start processing runs

### Reviewer
- View assigned cases
- Review extracted events
- Export data
- Cannot create clients or cases

## Troubleshooting

### "Invalid credentials" Error

**Symptoms:**
- Login modal shows "Invalid credentials" or "Incorrect password"
- Cannot log in with dev@localhost

**Solutions:**

1. **Verify exact credentials** (case-sensitive, no extra spaces):
   ```
   Email: dev@localhost
   Password: devpass123
   ```

2. **Check if user exists:**
   ```bash
   python scripts/seed_test_users.py
   ```

3. **Reset the password:**
   ```bash
   python scripts/reset_dev_password.py dev@localhost devpass123
   ```

4. **Check database connection:**
   ```bash
   # Verify DATABASE_URL in .env
   cat .env | grep DATABASE_URL
   
   # Test PostgreSQL connection
   psql -U legal_user -d legal_events -c "SELECT email FROM users;"
   ```

### "Cannot connect to API" Error

**Symptoms:**
- Login button does nothing
- Console shows network errors
- Can't reach http://localhost:8000

**Solutions:**

1. **Start the API server:**
   ```bash
   docker compose up -d api
   ```

2. **Check API is running:**
   ```bash
   curl http://localhost:8000/health
   ```

3. **Check logs:**
   ```bash
   docker compose logs api --tail=50
   ```

### "Account is disabled" Error

**Symptoms:**
- Login fails with "Account is disabled" message

**Solutions:**

1. **Activate the user account** (requires database access):
   ```sql
   UPDATE users SET is_active = true WHERE email = 'dev@localhost';
   ```

2. **Or recreate the user:**
   ```bash
   python scripts/seed_test_users.py
   ```

### Token Expired

**Symptoms:**
- Logged in successfully but getting 401 errors
- "Authentication required" errors

**Solutions:**

1. **Re-login** - Tokens expire after 24 hours by default
2. **Check token in browser console:**
   ```javascript
   console.log(localStorage.getItem('jwt_token'));
   ```
3. **Clear and re-login:**
   ```javascript
   localStorage.removeItem('jwt_token');
   // Then log in again
   ```

## Common Tasks

### List All Users
```bash
python -c "
import sys
sys.path.insert(0, '.')
from infra.database import SessionLocal
from infra.models import User

db = SessionLocal()
users = db.query(User).all()
for user in users:
    print(f'{user.email:<30} | {user.role.value:<15} | Active: {user.is_active}')
db.close()
"
```

### Create a New User (Python)
```python
from infra.database import SessionLocal
from infra.models import User, UserRole
from api.auth import get_password_hash

db = SessionLocal()
user = User(
    email="newuser@example.com",
    name="New User",
    role=UserRole.REVIEWER,
    password_hash=get_password_hash("securepassword123"),
    is_active=True
)
db.add(user)
db.commit()
db.close()
```

### Delete a User
```bash
python -c "
import sys
sys.path.insert(0, '.')
from infra.database import SessionLocal
from infra.models import User

db = SessionLocal()
user = db.query(User).filter(User.email == 'test@localhost').first()
if user:
    db.delete(user)
    db.commit()
    print(f'Deleted user: {user.email}')
else:
    print('User not found')
db.close()
"
```

## Security Best Practices

### Development
- ✅ Use default credentials for local testing
- ✅ Seed test users with `seed_test_users.py`
- ✅ Reset passwords freely with scripts
- ⚠️ Never commit real credentials to git

### Production
- ✅ Set strong, unique admin password
- ✅ Use environment variables for credentials
- ✅ Set `ENVIRONMENT=production` to disable dev endpoints
- ✅ Require HTTPS for all API access
- ✅ Rotate admin password regularly
- ✅ Use strong JWT secret key (32+ bytes)
- ❌ Never use default dev credentials
- ❌ Never enable dev password reset endpoints

## Environment Variables

```bash
# Required for all environments
JWT_SECRET_KEY=<64-char-hex-string>  # Generate with: openssl rand -hex 32

# Production/Staging only
ENVIRONMENT=production
ADMIN_EMAIL=admin@company.com
ADMIN_PASSWORD_HASH=$2b$12$...  # bcrypt hash
ADMIN_NAME="System Administrator"

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/legal_events
```

## API Endpoints

### Authentication
- `POST /v1/auth/login` - Login and get JWT token
- `POST /v1/auth/dev/reset-password` - Reset password (dev only)

### Users (Future)
- `POST /v1/users` - Create user (admin only)
- `GET /v1/users` - List users (admin only)
- `GET /v1/users/{user_id}` - Get user details
- `PUT /v1/users/{user_id}` - Update user
- `DELETE /v1/users/{user_id}` - Delete user (admin only)

## Support

For issues or questions:
1. Check this documentation
2. Review API logs: `docker compose logs api`
3. Check database: `psql -U legal_user -d legal_events`
4. Create an issue in the repository

## Related Documentation
- [Security Setup](SECURITY_SETUP.md)
- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [Operations Runbook](OPERATIONS_RUNBOOK.md)
