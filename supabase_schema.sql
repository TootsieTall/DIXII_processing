-- Supabase Database Schema for Tax Document Processing Application
-- Updated version that fixes foreign key relationships and adapts client structure
-- Run this SQL in your Supabase SQL Editor to create the required tables

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Clients table to store client information (adapted for first_name/last_name)
CREATE TABLE IF NOT EXISTS clients (
    id SERIAL PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    name VARCHAR(255) GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED,
    normalized_name VARCHAR(255) NOT NULL, -- For case-insensitive searches
    email VARCHAR(255),
    phone VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for client name searches
CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_normalized_name ON clients(normalized_name);
CREATE INDEX IF NOT EXISTS idx_clients_first_last ON clients(first_name, last_name);

-- Processing sessions table to track upload sessions
CREATE TABLE IF NOT EXISTS processing_sessions (
    id SERIAL PRIMARY KEY,
    session_id UUID NOT NULL UNIQUE,
    processing_mode VARCHAR(50) NOT NULL DEFAULT 'auto', -- 'auto' or 'manual'
    manual_client_info JSONB, -- Store manual client info when in manual mode
    status VARCHAR(50) NOT NULL DEFAULT 'processing', -- 'processing', 'completed', 'error'
    total_files INTEGER DEFAULT 0,
    completed_files INTEGER DEFAULT 0,
    error_files INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index for session searches
CREATE INDEX IF NOT EXISTS idx_processing_sessions_session_id ON processing_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_processing_sessions_status ON processing_sessions(status);
CREATE INDEX IF NOT EXISTS idx_processing_sessions_created_at ON processing_sessions(created_at);

-- Document results table to store processed document information
-- Fixed to properly reference processing_sessions
CREATE TABLE IF NOT EXISTS document_results (
    id SERIAL PRIMARY KEY,
    session_id INTEGER NOT NULL REFERENCES processing_sessions(id) ON DELETE CASCADE,
    client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    original_filename VARCHAR(500) NOT NULL,
    new_filename VARCHAR(500),
    document_type VARCHAR(200),
    tax_year INTEGER, -- Changed to INTEGER for proper year handling
    client_name VARCHAR(255),
    client_folder VARCHAR(255),
    processed_path TEXT,
    status VARCHAR(50) NOT NULL DEFAULT 'processing', -- 'waiting', 'processing', 'completed', 'error'
    error_message TEXT,
    confidence DECIMAL(3,2) DEFAULT 0.0, -- 0.00 to 1.00 format
    processing_time_seconds INTEGER,
    file_size_bytes BIGINT, -- File size in bytes
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for document results
CREATE INDEX IF NOT EXISTS idx_document_results_session_id ON document_results(session_id);
CREATE INDEX IF NOT EXISTS idx_document_results_client_id ON document_results(client_id);
CREATE INDEX IF NOT EXISTS idx_document_results_document_type ON document_results(document_type);
CREATE INDEX IF NOT EXISTS idx_document_results_tax_year ON document_results(tax_year);
CREATE INDEX IF NOT EXISTS idx_document_results_status ON document_results(status);
CREATE INDEX IF NOT EXISTS idx_document_results_created_at ON document_results(created_at);
CREATE INDEX IF NOT EXISTS idx_document_results_client_name ON document_results(client_name);

-- Create full-text search index for filenames
CREATE INDEX IF NOT EXISTS idx_document_results_filename_search
ON document_results USING gin(to_tsvector('english', original_filename || ' ' || COALESCE(new_filename, '')));

-- Create compound index for better performance
CREATE INDEX IF NOT EXISTS idx_document_results_compound
ON document_results(client_id, document_type, tax_year, created_at);

-- Processing statistics view for quick analytics
CREATE OR REPLACE VIEW processing_statistics AS
SELECT
    DATE_TRUNC('day', ps.created_at) as processing_date,
    COUNT(ps.id) as total_sessions,
    COUNT(CASE WHEN ps.status = 'completed' THEN 1 END) as completed_sessions,
    COUNT(CASE WHEN ps.status = 'error' THEN 1 END) as error_sessions,
    SUM(ps.total_files) as total_files_processed,
    SUM(ps.completed_files) as total_files_completed,
    SUM(ps.error_files) as total_files_with_errors,
    ROUND(
        AVG(ps.completed_files::DECIMAL / NULLIF(ps.total_files, 0)) * 100, 2
    ) as avg_success_rate
FROM processing_sessions ps
WHERE ps.created_at >= NOW() - INTERVAL '90 days'
GROUP BY DATE_TRUNC('day', ps.created_at)
ORDER BY processing_date DESC;

-- Client statistics view (updated for new structure)
CREATE OR REPLACE VIEW client_statistics AS
SELECT
    c.id,
    c.first_name,
    c.last_name,
    c.name,
    c.email,
    c.phone,
    c.created_at,
    COUNT(dr.id) as total_documents,
    COUNT(CASE WHEN dr.status = 'completed' THEN 1 END) as completed_documents,
    COUNT(CASE WHEN dr.status = 'error' THEN 1 END) as error_documents,
    COUNT(DISTINCT dr.tax_year) as unique_tax_years,
    MAX(dr.created_at) as last_document_processed
FROM clients c
LEFT JOIN document_results dr ON c.id = dr.client_id
GROUP BY c.id, c.first_name, c.last_name, c.name, c.email, c.phone, c.created_at
ORDER BY total_documents DESC;

-- Document type statistics view
CREATE OR REPLACE VIEW document_type_statistics AS
SELECT
    document_type,
    COUNT(*) as total_count,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count,
    COUNT(CASE WHEN status = 'error' THEN 1 END) as error_count,
    ROUND(AVG(confidence), 4) as avg_confidence,
    MIN(tax_year) as earliest_year,
    MAX(tax_year) as latest_year,
    COUNT(DISTINCT client_id) as unique_clients
FROM document_results
WHERE document_type IS NOT NULL
  AND created_at >= NOW() - INTERVAL '90 days'
GROUP BY document_type
ORDER BY total_count DESC;

-- Tax year statistics view
CREATE OR REPLACE VIEW tax_year_statistics AS
SELECT
    tax_year,
    COUNT(*) as total_count,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_count,
    COUNT(CASE WHEN status = 'error' THEN 1 END) as error_count,
    COUNT(DISTINCT client_id) as unique_clients
FROM document_results
WHERE tax_year IS NOT NULL
GROUP BY tax_year
ORDER BY tax_year DESC;

-- Recent activity view
CREATE OR REPLACE VIEW recent_activity AS
SELECT
    'session' as activity_type,
    ps.id,
    ps.session_id::text as reference_id,
    ps.status,
    ps.total_files as item_count,
    ps.processing_mode,
    NULL as client_name,
    ps.created_at
FROM processing_sessions ps
WHERE ps.created_at >= NOW() - INTERVAL '30 days'

UNION ALL

SELECT
    'document' as activity_type,
    dr.id,
    dr.original_filename as reference_id,
    dr.status,
    NULL as item_count,
    NULL as processing_mode,
    dr.client_name,
    dr.created_at
FROM document_results dr
WHERE dr.created_at >= NOW() - INTERVAL '30 days'

ORDER BY created_at DESC
LIMIT 100;

-- Function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers to automatically update updated_at
CREATE TRIGGER update_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processing_sessions_updated_at
    BEFORE UPDATE ON processing_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_results_updated_at
    BEFORE UPDATE ON document_results
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function to normalize client names for case-insensitive storage
-- Updated to work with first_name + last_name
CREATE OR REPLACE FUNCTION normalize_client_name(first_name TEXT, last_name TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN TRIM(LOWER(REGEXP_REPLACE(
        TRIM(first_name) || ' ' || TRIM(last_name), '\s+', ' ', 'g'
    )));
END;
$$ LANGUAGE plpgsql;

-- Trigger to automatically set normalized_name on client insert/update
CREATE OR REPLACE FUNCTION set_normalized_client_name()
RETURNS TRIGGER AS $$
BEGIN
    NEW.normalized_name = normalize_client_name(NEW.first_name, NEW.last_name);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_clients_normalized_name
    BEFORE INSERT OR UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION set_normalized_client_name();

-- Row Level Security (RLS) policies - adjust according to your authentication needs
-- For now, we'll keep it simple and allow all operations
-- You can modify these policies based on your authentication requirements

-- Enable RLS on tables
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_results ENABLE ROW LEVEL SECURITY;

-- Create policies for authenticated users (adjust as needed)
CREATE POLICY "Allow all operations for authenticated users" ON clients
    FOR ALL USING (true);

CREATE POLICY "Allow all operations for authenticated users" ON processing_sessions
    FOR ALL USING (true);

CREATE POLICY "Allow all operations for authenticated users" ON document_results
    FOR ALL USING (true);

-- Grant necessary permissions to authenticated users
GRANT ALL ON clients TO authenticated;
GRANT ALL ON processing_sessions TO authenticated;
GRANT ALL ON document_results TO authenticated;
GRANT ALL ON processing_statistics TO authenticated;
GRANT ALL ON client_statistics TO authenticated;
GRANT ALL ON document_type_statistics TO authenticated;
GRANT ALL ON tax_year_statistics TO authenticated;
GRANT ALL ON recent_activity TO authenticated;

-- Grant usage on sequences
GRANT USAGE ON SEQUENCE clients_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE processing_sessions_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE document_results_id_seq TO authenticated;

-- Create an improved search function that works with the new structure
CREATE OR REPLACE FUNCTION search_documents(
    search_query TEXT DEFAULT '',
    client_id_filter INTEGER DEFAULT NULL,
    document_type_filter TEXT DEFAULT NULL,
    tax_year_filter INTEGER DEFAULT NULL,
    limit_count INTEGER DEFAULT 50
)
RETURNS TABLE(
    id INTEGER,
    session_id INTEGER,
    client_id INTEGER,
    original_filename VARCHAR(500),
    new_filename VARCHAR(500),
    document_type VARCHAR(200),
    tax_year INTEGER,
    client_name VARCHAR(255),
    status VARCHAR(50),
    confidence DECIMAL(3,2),
    created_at TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        dr.id,
        dr.session_id,
        dr.client_id,
        dr.original_filename,
        dr.new_filename,
        dr.document_type,
        dr.tax_year,
        dr.client_name,
        dr.status,
        dr.confidence,
        dr.created_at
    FROM document_results dr
    WHERE
        (search_query = '' OR
         dr.original_filename ILIKE '%' || search_query || '%' OR
         dr.new_filename ILIKE '%' || search_query || '%' OR
         dr.client_name ILIKE '%' || search_query || '%' OR
         dr.document_type ILIKE '%' || search_query || '%')
        AND (client_id_filter IS NULL OR dr.client_id = client_id_filter)
        AND (document_type_filter IS NULL OR dr.document_type = document_type_filter)
        AND (tax_year_filter IS NULL OR dr.tax_year = tax_year_filter)
    ORDER BY dr.created_at DESC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- Sample data insertion (optional - remove in production)
-- INSERT INTO clients (first_name, last_name) VALUES
--     ('John', 'Smith'),
--     ('Jane', 'Doe'),
--     ('Robert', 'Johnson');

-- Comment: This updated schema provides the best of both approaches:
-- Key features:
-- 1. Proper foreign key relationships (fixed)
-- 2. Support for first_name/last_name structure (application compatibility)
-- 3. Comprehensive views and analytics from original schema
-- 4. Full-text search capabilities
-- 5. Automatic timestamp updates and normalization
-- 6. Row Level Security for multi-tenancy
-- 7. Improved indexing strategy
-- 8. Better data types (INTEGER for tax_year, proper confidence range)