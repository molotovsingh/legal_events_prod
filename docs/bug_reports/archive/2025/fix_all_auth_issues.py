#!/usr/bin/env python3
"""
Script to identify and document all endpoints that need authentication enforcement
"""

import re

# Read the main.py file
with open('/Users/aks/legal-events-production/api/main.py', 'r') as f:
    content = f.read()

# Find all endpoint definitions with current_user parameter
pattern = r'async def (\w+)\([^)]*current_user[^)]*\):'
matches = re.findall(pattern, content)

print("ENDPOINTS WITH current_user PARAMETER:")
print("=" * 60)

for func_name in matches:
    print(f"- {func_name}")

print("\n" + "=" * 60)
print("AUTHENTICATION ENFORCEMENT STATUS:")
print("=" * 60)

# Check each function for auth enforcement
for func_name in matches:
    # Find the function body
    func_pattern = rf'async def {func_name}\([^)]*\):[^{{]*{{[^}}]*}}'
    func_match = re.search(func_pattern, content, re.DOTALL)
    
    if func_match:
        func_body = func_match.group()
        
        # Check if it has auth enforcement
        has_auth_check = any([
            'if not current_user:' in func_body,
            'require_auth' in func_body,
            'require_admin' in func_body,
        ])
        
        status = "✅ Protected" if has_auth_check else "❌ VULNERABLE"
        print(f"{func_name}: {status}")

print("\n" + "=" * 60)
print("RECOMMENDED FIXES:")
print("=" * 60)

vulnerable_endpoints = [
    'create_client',
    'create_case', 
    'assign_user_to_case',
    'create_run',
    'start_run'
]

print("""
All endpoints that mutate state should enforce authentication:

1. Add this check at the start of each endpoint:
   ```python
   if not current_user:
       raise HTTPException(
           status_code=401,
           detail="Authentication required",
           headers={"WWW-Authenticate": "Bearer"},
       )
   ```

2. Or use the require_auth dependency:
   ```python
   current_user: User = Depends(require_auth)
   ```

Vulnerable endpoints that need fixing:""")
for endpoint in vulnerable_endpoints:
    print(f"  - {endpoint}")