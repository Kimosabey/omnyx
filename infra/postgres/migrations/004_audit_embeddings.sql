-- =============================================================
-- OMNYX Primary DB — Migration 004: Audit & Embeddings
-- =============================================================

-- Append-only audit log
CREATE TABLE audit.events (
  id         BIGSERIAL PRIMARY KEY,
  actor      TEXT NOT NULL,
  action     TEXT NOT NULL,
  target     TEXT,
  payload    JSONB NOT NULL DEFAULT '{}',
  tenant_id  TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- pgvector embeddings (conditional on extension availability)
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    EXECUTE $sql$
      CREATE TABLE embeddings.knowledge_chunks (
        id          BIGSERIAL PRIMARY KEY,
        doc_id      TEXT NOT NULL REFERENCES app.knowledge_docs(id) ON DELETE CASCADE,
        tenant_id   TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        content     TEXT NOT NULL,
        embedding   vector(1536),
        metadata    JSONB NOT NULL DEFAULT '{}',
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
      );

      CREATE INDEX knowledge_chunks_embedding_idx
        ON embeddings.knowledge_chunks
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    $sql$;
  ELSE
    EXECUTE $sql$
      CREATE TABLE embeddings.knowledge_chunks (
        id          BIGSERIAL PRIMARY KEY,
        doc_id      TEXT NOT NULL REFERENCES app.knowledge_docs(id) ON DELETE CASCADE,
        tenant_id   TEXT NOT NULL,
        chunk_index INTEGER NOT NULL,
        content     TEXT NOT NULL,
        metadata    JSONB NOT NULL DEFAULT '{}',
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
      );
    $sql$;
    RAISE NOTICE 'embeddings.knowledge_chunks created WITHOUT vector column (pgvector missing)';
  END IF;
END $$;
