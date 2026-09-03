-- Enterprise AI Agent Database Initialization
-- Enables pgvector extension and creates core tables

-- Enable pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Create users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255) NOT NULL,
    role VARCHAR(50) DEFAULT 'user',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(500) NOT NULL,
    file_type VARCHAR(50) NOT NULL,
    file_size INTEGER NOT NULL,
    content_hash VARCHAR(64) NOT NULL,
    status VARCHAR(50) DEFAULT 'uploaded',
    raw_content TEXT,
    chunk_count INTEGER DEFAULT 0,
    uploaded_by UUID REFERENCES users(id),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    indexed_at TIMESTAMP WITH TIME ZONE,
    metadata JSONB DEFAULT '{}'
);

-- Create document chunks table with pgvector
CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1536),
    chunk_index INTEGER NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create chat sessions table
CREATE TABLE IF NOT EXISTS chat_sessions (
    id VARCHAR(64) PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id),
    title VARCHAR(500) DEFAULT 'New Conversation',
    message_count INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    total_cost FLOAT DEFAULT 0.0,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create query logs table for observability
CREATE TABLE IF NOT EXISTS query_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id VARCHAR(64) NOT NULL,
    user_id UUID NOT NULL,
    query TEXT NOT NULL,
    response TEXT,
    retrieval_method VARCHAR(50),
    chunks_retrieved INTEGER DEFAULT 0,
    tools_called JSONB DEFAULT '[]',
    citations JSONB DEFAULT '[]',
    latency_ms FLOAT,
    input_tokens INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    cost_usd FLOAT DEFAULT 0.0,
    hallucination_score FLOAT,
    injection_detected BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create evaluation runs table
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    dataset_name VARCHAR(100) NOT NULL,
    num_samples INTEGER NOT NULL,
    faithfulness FLOAT,
    answer_relevance FLOAT,
    context_recall FLOAT,
    context_precision FLOAT,
    avg_latency_ms FLOAT,
    total_cost_usd FLOAT DEFAULT 0.0,
    results JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_content_hash ON documents(content_hash);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_query_logs_session ON query_logs(session_id);
CREATE INDEX IF NOT EXISTS idx_query_logs_created ON query_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_user ON chat_sessions(user_id);

-- Create vector similarity index (IVFFlat)
-- Note: This requires data to be loaded first for optimal lists count
-- For initial setup, we use a basic index
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_indexes 
        WHERE tablename = 'document_chunks' AND indexname = 'chunk_embedding_idx'
    ) THEN
        -- Only create if we have enough data
        IF (SELECT COUNT(*) FROM document_chunks) > 100 THEN
            CREATE INDEX chunk_embedding_idx 
            ON document_chunks 
            USING ivfflat (embedding vector_cosine_ops) 
            WITH (lists = 100);
        END IF;
    END IF;
END $$;

-- Create full-text search index
CREATE INDEX IF NOT EXISTS idx_chunks_content_fts 
ON document_chunks 
USING gin(to_tsvector('english', content));
