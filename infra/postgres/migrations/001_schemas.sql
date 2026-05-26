-- =============================================================
-- OMNYX Primary DB — Migration 001: Schemas & Extensions
-- PostgreSQL 16 + pgvector (no TimescaleDB on this instance)
-- =============================================================

CREATE SCHEMA IF NOT EXISTS source;       -- Unicharm IBMS mirror (system of record for source data)
CREATE SCHEMA IF NOT EXISTS app;          -- OMNYX operational (equipment, alerts, work orders)
CREATE SCHEMA IF NOT EXISTS audit;        -- Append-only audit trail
CREATE SCHEMA IF NOT EXISTS embeddings;   -- pgvector AI embeddings (knowledge RAG)

-- Extensions
CREATE EXTENSION IF NOT EXISTS pg_stat_statements;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS btree_gin; -- composite GIN indexes

-- pgvector — gracefully skip if not installed
DO $$ BEGIN
  CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION WHEN undefined_file THEN
  RAISE NOTICE 'pgvector not available — AI embedding features disabled';
END $$;

-- Helpful comment metadata
COMMENT ON SCHEMA source     IS 'Unicharm IBMS source-of-truth — DDC registry, point catalog, historical readings & alarms';
COMMENT ON SCHEMA app        IS 'OMNYX operational data — equipment, alerts, work orders, AI workflows';
COMMENT ON SCHEMA audit      IS 'Append-only audit log of every state change';
COMMENT ON SCHEMA embeddings IS 'pgvector embeddings for RAG knowledge retrieval';
