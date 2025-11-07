# Alembic Enum Migration Strategy

## Overview

This project uses native PostgreSQL enums for type safety (e.g., `userrole`, `runstatus`, `documentstatus`, `clientstatus`, `casestatus`). When modifying enum values, special care is required because Alembic's autogenerate doesn't handle enum changes automatically.

## Current Enums in the System

From `migrations/versions/001_initial_schema.py` and `api/models.py`:

1. **UserRole**: `admin`, `case_manager`, `reviewer`
2. **RunStatus**: `queued`, `processing`, `partial`, `success`, `failed`
3. **DocumentStatus**: `pending`, `processing`, `success`, `failed`
4. **ClientStatus**: `active`, `inactive`, `archived`
5. **CaseStatus**: `active`, `archived`

## The Problem

PostgreSQL native enums have limitations:
- You cannot add/remove/rename values within a transaction (in most PostgreSQL versions)
- Alembic `alembic revision --autogenerate` does not detect enum changes
- Direct ALTER TYPE commands may fail if the type is in use
- Renaming values requires complex workarounds

## Safe Migration Patterns

### Pattern 1: Adding a New Enum Value (Transactional - PostgreSQL 12+)

**Use Case**: Adding `partial_success` to RunStatus

```python
"""Add partial_success to RunStatus enum

Revision ID: 003_add_partial_success
Revises: 002_xxx
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # PostgreSQL 12+ supports adding enum values in a transaction
    op.execute("ALTER TYPE runstatus ADD VALUE IF NOT EXISTS 'partial_success'")

def downgrade():
    # WARNING: Removing enum values is not straightforward
    # See Pattern 4 for safe removal strategy
    pass
```

**Notes**:
- PostgreSQL 12+ allows `ADD VALUE` in transactions
- PostgreSQL 9.x-11.x requires committing before adding the value (use `op.execute("COMMIT")`)
- Use `IF NOT EXISTS` to make migration idempotent

### Pattern 2: Renaming an Enum Value (Non-Transactional)

**Use Case**: Renaming `partial` to `partial_success` in RunStatus

PostgreSQL does not support renaming enum values directly. Use this workaround:

```python
"""Rename RunStatus 'partial' to 'partial_success'

Revision ID: 004_rename_partial
Revises: 003_xxx
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Step 1: Add new value
    op.execute("ALTER TYPE runstatus ADD VALUE IF NOT EXISTS 'partial_success'")

    # Step 2: Update all existing rows
    op.execute("""
        UPDATE runs
        SET status = 'partial_success'::runstatus
        WHERE status = 'partial'::runstatus
    """)

    # Step 3: Remove old value (see Pattern 4)
    # Note: This requires creating a new type and swapping columns

def downgrade():
    # Reverse: update rows back to 'partial'
    op.execute("""
        UPDATE runs
        SET status = 'partial'::runstatus
        WHERE status = 'partial_success'::runstatus
    """)
    # Note: Removing 'partial_success' requires Pattern 4
```

**Notes**:
- Renaming is a multi-step process: add, update, (optionally) remove
- Consider leaving old values in place if removal is risky
- Always verify data migration with SELECT queries before/after

### Pattern 3: Removing an Enum Value (Requires Type Recreation)

**Use Case**: Removing unused `inactive` from ClientStatus

Removing enum values safely requires recreating the type:

```python
"""Remove 'inactive' from ClientStatus enum

Revision ID: 005_remove_inactive
Revises: 004_xxx
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Step 1: Verify no rows use the value
    connection = op.get_bind()
    result = connection.execute(sa.text("""
        SELECT COUNT(*) FROM clients WHERE status = 'inactive'
    """))
    count = result.scalar()
    if count > 0:
        raise Exception(f"Cannot remove 'inactive': {count} rows still use it")

    # Step 2: Convert column to TEXT
    op.execute("ALTER TABLE clients ALTER COLUMN status TYPE TEXT")

    # Step 3: Drop old enum type
    op.execute("DROP TYPE IF EXISTS clientstatus CASCADE")

    # Step 4: Create new enum type (without 'inactive')
    op.execute("""
        CREATE TYPE clientstatus AS ENUM ('active', 'archived')
    """)

    # Step 5: Convert column back to enum
    op.execute("""
        ALTER TABLE clients
        ALTER COLUMN status TYPE clientstatus USING status::clientstatus
    """)

def downgrade():
    # Reverse: Add 'inactive' back
    op.execute("ALTER TABLE clients ALTER COLUMN status TYPE TEXT")
    op.execute("DROP TYPE IF EXISTS clientstatus CASCADE")
    op.execute("""
        CREATE TYPE clientstatus AS ENUM ('active', 'inactive', 'archived')
    """)
    op.execute("""
        ALTER TABLE clients
        ALTER COLUMN status TYPE clientstatus USING status::clientstatus
    """)
```

**Notes**:
- Always verify no rows use the value before removal
- This pattern is **non-transactional** and requires careful testing
- Backup data before applying this migration in production

### Pattern 4: Safe Alternative - Use Constraints Instead of Removing

Instead of removing enum values, add a CHECK constraint to prevent new usage:

```python
"""Deprecate 'inactive' in ClientStatus

Revision ID: 006_deprecate_inactive
Revises: 005_xxx
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Add constraint to prevent new 'inactive' values
    op.create_check_constraint(
        'ck_client_status_no_inactive',
        'clients',
        "status != 'inactive'"
    )

    # Update existing rows (if any)
    op.execute("""
        UPDATE clients
        SET status = 'archived'
        WHERE status = 'inactive'
    """)

def downgrade():
    op.drop_constraint('ck_client_status_no_inactive', 'clients')
```

**Notes**:
- Safer than removing the enum value entirely
- Allows existing migrations to still reference the value
- Can be combined with data migration to phase out usage

## Helper Libraries

Consider using these libraries for safer enum migrations:

1. **alembic-postgresql-enum** (https://github.com/RazerM/alembic-postgresql-enum)
   - Automates enum synchronization
   - Handles add/remove/rename operations

2. **alembic-enums** (https://github.com/Quantco/alembic-enums)
   - Provides helpers for enum migrations
   - Better autogenerate detection

## Testing Enum Migrations

### Local Testing Workflow

```bash
# 1. Create migration
alembic revision -m "add partial_success to RunStatus"

# 2. Edit migration file with appropriate pattern

# 3. Apply migration
alembic upgrade head

# 4. Verify enum values
docker exec legal_events_db psql -U postgres -d legal_events -c "
  SELECT enum_range(NULL::runstatus);
"

# 5. Test downgrade
alembic downgrade -1

# 6. Test upgrade again
alembic upgrade head
```

### Verification Queries

```sql
-- List all enum types and their values
SELECT t.typname, e.enumlabel
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
WHERE t.typname IN ('userrole', 'runstatus', 'documentstatus', 'clientstatus', 'casestatus')
ORDER BY t.typname, e.enumsortorder;

-- Check column dependencies on enum types
SELECT
    n.nspname AS schema,
    t.typname AS enum_type,
    c.relname AS table_name,
    a.attname AS column_name
FROM pg_type t
JOIN pg_enum e ON t.oid = e.enumtypid
JOIN pg_attribute a ON a.atttypid = t.oid
JOIN pg_class c ON a.attrelid = c.oid
JOIN pg_namespace n ON c.relnamespace = n.oid
WHERE t.typname IN ('userrole', 'runstatus', 'documentstatus', 'clientstatus', 'casestatus')
ORDER BY t.typname, c.relname, a.attname;

-- Count usage of specific enum values
SELECT status, COUNT(*) FROM runs GROUP BY status;
SELECT status, COUNT(*) FROM documents GROUP BY status;
SELECT role, COUNT(*) FROM users GROUP BY role;
```

## Best Practices

1. **Always test migrations locally first**
   - Use `docker compose down && docker compose up` to test from scratch
   - Verify both upgrade and downgrade paths

2. **Document breaking changes**
   - Add comments in migration explaining why changes are needed
   - Update CHANGELOG.md with enum changes

3. **Use transactional patterns when possible**
   - PostgreSQL 12+ supports transactional enum additions
   - For older versions, use explicit COMMIT

4. **Avoid removing enum values in production**
   - Instead, add new values and migrate data
   - Use CHECK constraints to deprecate old values
   - Keep old values for backward compatibility

5. **Always verify data before migrations**
   - Run SELECT queries to check usage of enum values
   - Ensure no rows depend on values being removed

6. **Consider using SQLAlchemy native_enum=False**
   - For highly volatile enums, use `Enum(..., native_enum=False)`
   - This stores enums as VARCHAR with CHECK constraints
   - Easier to modify but loses some type safety

## Example: Complete Enum Refactoring

Let's say we want to refactor RunStatus from:
- `queued`, `processing`, `partial`, `success`, `failed`

To:
- `queued`, `processing`, `partial_success`, `success`, `failed`, `cancelled`

**Migration Plan**:

```python
"""Refactor RunStatus enum

Revision ID: 007_refactor_runstatus
Revises: 006_xxx
"""

from alembic import op
import sqlalchemy as sa

def upgrade():
    # Step 1: Add new values
    op.execute("ALTER TYPE runstatus ADD VALUE IF NOT EXISTS 'partial_success'")
    op.execute("ALTER TYPE runstatus ADD VALUE IF NOT EXISTS 'cancelled'")

    # Step 2: Migrate data from 'partial' to 'partial_success'
    op.execute("""
        UPDATE runs
        SET status = 'partial_success'::runstatus
        WHERE status = 'partial'::runstatus
    """)

    # Step 3: (Optional) Remove 'partial' using Pattern 3 if needed
    # For safety, we'll leave it and add a deprecation comment

def downgrade():
    # Migrate data back
    op.execute("""
        UPDATE runs
        SET status = 'partial'::runstatus
        WHERE status = 'partial_success'::runstatus
    """)

    op.execute("""
        UPDATE runs
        SET status = 'failed'::runstatus
        WHERE status = 'cancelled'::runstatus
    """)

    # Note: We don't remove 'partial_success' or 'cancelled' to avoid complexity
```

## References

- [PostgreSQL Enum Types Documentation](https://www.postgresql.org/docs/current/datatype-enum.html)
- [Alembic Operations Reference](https://alembic.sqlalchemy.org/en/latest/ops.html)
- [SQLAlchemy Enum Types](https://docs.sqlalchemy.org/en/20/core/type_basics.html#sqlalchemy.types.Enum)
- [alembic-postgresql-enum on GitHub](https://github.com/RazerM/alembic-postgresql-enum)
