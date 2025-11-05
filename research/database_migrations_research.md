# Database & Migration Research

This document provides comprehensive research findings on database schema evolution and migration strategies for production systems, with a focus on PostgreSQL and SQLAlchemy best practices.

## 1. PostgreSQL ENUM Evolution Strategies

### Safe ENUM Value Addition

**Current PostgreSQL Support:**
- `ALTER TYPE ... ADD VALUE 'new_value' [BEFORE|AFTER] 'existing_value'`
- `ALTER TYPE ... RENAME VALUE 'old_value' TO 'new_value'`
- `IF NOT EXISTS` clause available for safe additions

**Production-Safe Migration Pattern:**
```sql
-- Step 1: Add new enum value
ALTER TYPE status_enum ADD VALUE 'archived' IF NOT EXISTS;

-- Step 2: Update application code to handle new value
-- (Deploy application update)

-- Step 3: Update data to use new value where appropriate
UPDATE cases SET status = 'archived' WHERE condition = 'old_status';

-- Step 4: (Optional) Remove old value after transition period
ALTER TYPE status_enum DROP VALUE 'deprecated_status';
```

**Zero-Downtime Strategy:**
1. **Backward Compatibility:** New enum values added at the end maintain existing code compatibility
2. **Gradual Migration:** Use transitional periods where both old and new values are valid
3. **Application Logic:** Update application to handle all enum values, not just new ones
4. **Testing:** Verify enum ordering doesn't break existing queries

### ENUM Evolution Best Practices

- **Avoid ENUM re-creation** in production - requires table rebuilds and exclusive locks
- **Use explicit transactions** for enum modifications
- **Document enum semantics** - ordering matters for certain PostgreSQL operations
- **Consider using CHECK constraints** for complex validation rules instead of enums when possible

## 2. SQLAlchemy 2.0 Migration Path

### Declarative Base Deprecation

**Old Pattern (Deprecated):**
```python
from sqlalchemy.ext.declarative import declarative_base
Base = declarative_base()
```

**New Pattern (SQLAlchemy 2.0+):**
```python
from sqlalchemy.orm import DeclarativeBase
class Base(DeclarativeBase):
    pass
```

**Migration Strategy:**
1. **Update imports** across the codebase
2. **Use `__allow_unmapped__`** for legacy code during transition
3. **Enable warnings** with `SQLALCHEMY_WARN_20=1` to identify deprecated patterns
4. **Test thoroughly** with both old and new patterns

### Key Changes in SQLAlchemy 2.0

- **Removal of legacy patterns:** Connectionless execution, implicit autocommit
- **New Result objects:** Row objects behave like named tuples
- **Unified select() API:** Core and ORM now use same select() construct
- **Session changes:** Explicit transaction control required
- **PEP 484 support:** Enhanced typing annotations with `Mapped` type

## 3. PostgreSQL JSON vs JSONB Performance

### Performance Comparison

| Characteristic | JSON | JSONB |
|-------------|------|-------|
| Storage | Exact text copy | Decomposed binary format |
| Processing | Slower (reparse needed) | Faster (no reparsing) |
| Indexing | No GIN support | GIN indexing supported |
| Whitespace | Preserved | Not preserved |
| Key Order | Preserved | Not preserved |
| Duplicates | Kept | Last value kept |

### Indexing Strategies

**JSONB GIN Index Types:**
```sql
-- Default GIN index (all operations)
CREATE INDEX idx_data_jsonb ON documents USING GIN (data_column);

-- Path-specific GIN (smaller, faster for specific paths)
CREATE INDEX idx_data_jsonb_path ON documents USING GIN (data_column jsonb_path_ops);

-- Expression index for specific fields
CREATE INDEX idx_data_jsonb_user_id ON documents USING GIN ((data_column -> 'user_id'));
```

### Recommendations for run_metadata Column

**Use JSONB because:**
- **Query Performance:** Supports containment operators (`@>`, `?`, `@@`)
- **Indexing:** GIN indexes enable efficient JSON queries
- **Storage Efficiency:** Binary format is more compact
- **Update Performance:** Better performance for partial updates

**Migration Strategy:**
```sql
-- Step 1: Add new JSONB column
ALTER TABLE documents ADD COLUMN data_jsonb JSONB;

-- Step 2: Migrate data (application-level migration)
UPDATE documents SET data_jsonb = data_json::jsonb WHERE data_json IS NOT NULL;

-- Step 3: Create indexes
CREATE INDEX idx_data_jsonb ON documents USING GIN (data_jsonb);

-- Step 4: Drop old column (after verification)
ALTER TABLE documents DROP COLUMN data_json;
```

## 4. Event Tables Retention & Partitioning

### Partitioning Strategy for High-Volume Event Tables

**Recommended Approach: Range Partitioning by Time**
```sql
CREATE TABLE events (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMP NOT NULL,
    event_data JSONB NOT NULL,
    -- Other columns...
) PARTITION BY RANGE (created_at);

-- Monthly partitions example
CREATE TABLE events_2024_01 PARTITION OF events
    FOR VALUES FROM ('2024-01-01') TO ('2024-02-01');

CREATE TABLE events_2024_02 PARTITION OF events
    FOR VALUES FROM ('2024-02-01') TO ('2024-03-01');
```

### Automated Retention Policy

**PostgreSQL Function for Partition Management:**
```sql
CREATE OR REPLACE FUNCTION create_monthly_partitions()
RETURNS VOID AS $$
BEGIN
    -- Create next month's partition if needed
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables 
        WHERE table_name = 'events_' || to_char(date_trunc(current_date + interval '1 month'), 'YYYY_MM')
    ) THEN
        EXECUTE format('CREATE TABLE IF NOT EXISTS events_%s PARTITION OF events FOR VALUES FROM (%L) TO (%L)', 
            to_char(date_trunc(current_date + interval '1 month'), 'YYYY_MM'),
            to_char(date_trunc(current_date + interval '2 months'), 'YYYY_MM')
        );
    END IF;
    
    -- Drop old partitions (older than 6 months)
    FOR old_partition IN 
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_name LIKE 'events_%' 
          AND table_name < 'events_' || to_char(date_trunc(current_date - interval '6 months'), 'YYYY_MM')
    LOOP
        EXECUTE 'DROP TABLE IF EXISTS ' || old_partition;
    END LOOP;
END;
$$ LANGUAGE plpgsql;
```

### Retention Implementation Options

**Option 1: Partition Dropping**
- **Pros:** Instant data removal, minimal storage overhead
- **Cons:** Requires careful coordination, potential data loss if misconfigured

**Option 2: Archive Tables**
- **Pros:** Data preserved, can restore if needed
- **Cons:** Additional storage complexity, slower queries across archive

**Option 3: Soft Deletes with Status Column**
- **Pros:** Simple to implement, data recoverable
- **Cons:** Table size grows, query performance degradation

### Monitoring and Maintenance

**Essential Queries:**
```sql
-- Monitor partition sizes
SELECT 
    schemaname||'.'||tablename as table_name,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    pg_total_relation_size(schemaname||'.'||tablename) as total_size
FROM information_schema.tables 
WHERE tablename LIKE 'events_%';

-- Monitor partition pruning effectiveness
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM events WHERE created_at > NOW() - INTERVAL '30 days';
```

## 5. Implementation Recommendations

### Migration Framework Integration

**Alembic Migration Structure:**
```python
"""Add new enum value safely."""
from alembic import op
from sqlalchemy import text

def upgrade():
    # Add new enum value
    op.execute(text("ALTER TYPE case_status_enum ADD VALUE 'settled' IF NOT EXISTS"))
    
    # Update application logic first
    # Then migrate data as needed

def downgrade():
    # Remove new enum value
    op.execute(text("ALTER TYPE case_status_enum DROP VALUE 'settled'"))
```

### Testing Strategy

**Pre-Deployment Checklist:**
1. **Schema Validation:** Verify all enum changes work in staging
2. **Performance Testing:** Benchmark JSONB queries with realistic data volumes
3. **Rollback Testing:** Test downgrade procedures thoroughly
4. **Application Testing:** Verify application handles all enum values correctly

### Production Deployment

**Blue-Green Deployment:**
1. **Database Backup:** Full backup before schema changes
2. **Zero-Downtime Migration:** Use additive changes where possible
3. **Gradual Rollout:** Feature flags to control new enum usage
4. **Monitoring:** Enhanced monitoring during deployment window

**Rollback Plan:**
1. **Immediate Rollback:** Use downgrade scripts if issues detected
2. **Data Recovery:** Restore from backup if schema corruption occurs
3. **Application Rollback:** Revert to previous version if needed

## 6. Tools and Automation

### Recommended Tooling

**Schema Management:**
- **Alembic:** For database migrations
- **pgAdmin:** For PostgreSQL administration
- **Custom Scripts:** For automated partition management

### Monitoring Setup

**Key Metrics:**
- Query performance before/after changes
- Partition sizes and growth rates
- Index usage statistics
- Migration execution times

### Automation Opportunities

- **Scheduled partition creation** based on data growth
- **Automated retention** for old event data
- **Alerting** for unusual enum value usage patterns

---

*This research should be reviewed and adapted based on specific application requirements, data volumes, and availability requirements before implementation.*