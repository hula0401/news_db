# Database Fix Documentation

## 2025-11-18 16:00: stock_news table adjustment for LIFO stack compatibility
Fixed SQL script to properly drop UNIQUE constraint before recreating as composite index.

---

## Issue: DROP INDEX fails for constraint-backed index

**Error:**
```
ERROR: cannot drop index stock_news_url_key because constraint stock_news_url_key on table stock_news requires it
```

**Root Cause:**
`stock_news_url_key` is a UNIQUE constraint, not a standalone index. Constraints must be dropped with `ALTER TABLE ... DROP CONSTRAINT`.

**Fix:**
```sql
-- Wrong:
DROP INDEX IF EXISTS stock_news_url_key;

-- Correct:
ALTER TABLE stock_news DROP CONSTRAINT IF EXISTS stock_news_url_key;
```

**Applied in:** `adjust_stock_news_table.sql` line 64

---

## Schema Changes Required

### Missing Columns (4):
- `source_id` UUID - news source reference
- `external_id` TEXT - API external IDs
- `metadata` JSONB - flexible additional data
- `updated_at` TIMESTAMPTZ - auto-updated timestamp

### Constraint Fixes (2):
- `published_at` → NOT NULL (currently nullable)
- `created_at` → NOT NULL (currently nullable)

### Index Changes (3):
- DROP constraint `stock_news_url_key` (UNIQUE on url)
- ADD index `idx_stock_news_symbol_url` (UNIQUE on symbol+url)
- ADD index `idx_stock_news_symbol_position` (critical for stack queries)

### Helper Functions (1):
- `increment_news_positions(p_symbol TEXT)` - increments all positions for LIFO stack

---

## Migration File

**File:** `adjust_stock_news_table.sql`
**Status:** Ready to run
**Safe:** Yes - only adds columns/indexes, no data loss
