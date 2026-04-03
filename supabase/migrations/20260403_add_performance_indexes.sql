-- Migration: Add performance indexes for pgvector, audit_log, and document_embeddings

-- 1. ivfflat index for pgvector cosine similarity
--    lists=100 is good up to ~1M rows; tune to sqrt(row_count)
CREATE INDEX IF NOT EXISTS idx_document_embeddings_vector
ON document_embeddings
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);

-- 2. Partial index for RAG memory queries
--    Covers: last 20 ai_chat events per workspace+user
CREATE INDEX IF NOT EXISTS idx_audit_log_ai_memory
ON audit_log (workspace_id, user_id, created_at DESC)
WHERE action = 'ai_chat';

-- 3. General audit_log query index
CREATE INDEX IF NOT EXISTS idx_audit_log_workspace_created
ON audit_log (workspace_id, created_at DESC);

-- 4. Store which model produced each embedding (for future multi-model support)
ALTER TABLE document_embeddings
ADD COLUMN IF NOT EXISTS embedding_model text NOT NULL DEFAULT 'text-embedding-3-small';

CREATE INDEX IF NOT EXISTS idx_document_embeddings_model
ON document_embeddings (workspace_id, embedding_model);
