# Security Fix Summary: Authentication Enforcement

## Critical Issue Fixed

**[P1] Authentication Not Enforced on State-Mutating Endpoints**

### Problem
The retry endpoint and several other critical endpoints accept the `current_user` dependency but don't verify if the user is actually authenticated. Since `get_current_user` returns `None` when no token is provided (due to `auto_error=False`), these endpoints allow anonymous access to sensitive operations.

### Affected Endpoints - ALL FIXED ✅

1. **`PUT /v1/runs/{run_id}/retry`** - ✅ FIXED (explicit check)
   - Could reset document statuses and trigger re-processing
   - Now enforces authentication with explicit 401 check

2. **`POST /v1/clients`** - ✅ FIXED (require_auth dependency)
   - Creates client organizations
   - Now uses `Depends(require_auth)` to enforce authentication

3. **`POST /v1/cases`** - ✅ FIXED (require_auth dependency)
   - Creates legal cases
   - Now uses `Depends(require_auth)` to enforce authentication

4. **`POST /v1/cases/{case_id}/assign`** - ✅ FIXED (require_auth dependency)
   - Assigns users to cases
   - Now uses `Depends(require_auth)` to enforce authentication

5. **`POST /v1/runs`** - ✅ FIXED (require_auth dependency)
   - Creates processing runs
   - Now uses `Depends(require_auth)` to enforce authentication

6. **`PUT /v1/runs/{run_id}/start`** - ✅ FIXED (require_auth dependency)
   - Starts document processing
   - Now uses `Depends(require_auth)` to enforce authentication

## Fix Applied

### Implementation Approach Used

Instead of adding manual checks to each endpoint, we used the cleaner `require_auth` dependency injection approach:

**Changed from:**
```python
current_user: User = Depends(get_current_user)  # Returns None if no auth
```

**Changed to:**
```python
current_user: User = Depends(require_auth)  # Raises 401 if no auth
```

This approach:
- Is more maintainable (DRY principle)
- Enforces authentication at the dependency level
- Uses FastAPI's idiomatic patterns
- Prevents accidentally forgetting the check

### Endpoints Fixed:
1. `/v1/runs/{run_id}/retry` - Explicit check added (line 568-576)
2. `/v1/clients` - Uses `require_auth` dependency
3. `/v1/cases` - Uses `require_auth` dependency  
4. `/v1/cases/{case_id}/assign` - Uses `require_auth` dependency
5. `/v1/runs` - Uses `require_auth` dependency
6. `/v1/runs/{run_id}/start` - Uses `require_auth` dependency

### Helper Function Added
```python
# api/auth.py - Lines 135-156
async def require_auth(
    current_user: Optional[User] = Depends(get_current_user)
) -> User:
    """Require authentication (any valid user)"""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user
```

## Recommended Immediate Actions

### Option 1: Quick Fix (Add auth checks to each endpoint)
Add the same authentication check to all vulnerable endpoints:

```python
if not current_user:
    raise HTTPException(
        status_code=401,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
```

### Option 2: Better Fix (Use require_auth dependency)
Change the dependency injection from:
```python
current_user: User = Depends(get_current_user)
```

To:
```python
current_user: User = Depends(require_auth)
```

This ensures authentication is enforced at the dependency level.

## Testing the Fix

### Test Script Created
`test_auth_fix.py` - Verifies authentication is enforced

### Manual Testing
```bash
# Test without authentication (should fail with 401)
curl -X PUT http://localhost:8000/v1/runs/1/retry

# Test with invalid token (should fail with 401)
curl -X PUT http://localhost:8000/v1/runs/1/retry \
  -H "Authorization: Bearer invalid_token"

# Test with valid token (should work)
curl -X PUT http://localhost:8000/v1/runs/1/retry \
  -H "Authorization: Bearer <valid_jwt_token>"
```

## Security Impact

### Before Fix
- Any unauthenticated user could:
  - Retry failed runs (triggering compute costs)
  - Create clients and cases
  - Start document processing
  - Assign users to cases

### After Fix (Retry Endpoint Only)
- Retry endpoint now requires valid JWT authentication
- Other endpoints still need fixing

## Compliance Notes

- **Service Boundaries**: ✅ Maintained - Auth is API's responsibility
- **Event-Driven**: ✅ Compatible - Auth happens before event emission
- **Idempotency**: ✅ Preserved - Auth check is idempotent

## Priority

**CRITICAL**: The remaining vulnerable endpoints should be fixed immediately as they allow unauthorized state mutations and could lead to:
- Data tampering
- Resource exhaustion (compute costs)
- Privacy violations (unauthorized case access)
- Audit trail corruption (anonymous actions logged)

## Root Cause

The issue stems from:
1. `get_current_user` being designed as optional (returns `None` for missing auth)
2. Endpoints not checking if `current_user` is `None` before proceeding
3. Using pattern `current_user.email if current_user else "anonymous"` which silently allows anonymous access

## Prevention

1. **Code Review**: Check all endpoints with `current_user` parameter
2. **Testing**: Add auth tests for all state-mutating endpoints
3. **Policy**: Never allow optional auth on mutation endpoints
4. **Linting**: Consider custom rule to flag unchecked `current_user` usage