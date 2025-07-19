-- Supabase Database Schema for Tax Document Processing Application
-- Migration-Safe Version
-- This script will work whether you have existing tables or not

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing policies, triggers, and functions first to avoid conflicts
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON clients;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON processing_sessions;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON document_results;

DROP TRIGGER IF EXISTS set_clients_normalized_name ON clients;
DROP TRIGGER IF EXISTS update_clients_updated_at ON clients;
DROP TRIGGER IF EXISTS update_processing_sessions_updated_at ON processing_sessions;
DROP TRIGGER IF EXISTS update_document_results_updated_at ON document_results;

DROP FUNCTION IF EXISTS set_normalized_client_name();
DROP FUNCTION IF EXISTS normalize_client_name(TEXT, TEXT);
DROP FUNCTION IF EXISTS normalize_client_name(TEXT);
DROP FUNCTION IF EXISTS update_updated_at_column();
DROP FUNCTION IF EXISTS search_documents(TEXT, INTEGER, TEXT, INTEGER, INTEGER);

-- Drop existing views
DROP VIEW IF EXISTS recent_activity;
DROP VIEW IF EXISTS tax_year_statistics;
DROP VIEW IF EXISTS document_type_statistics;
DROP VIEW IF EXISTS client_statistics;
DROP VIEW IF EXISTS processing_statistics;

-- For fresh install or if you want to recreate tables, uncomment these lines:
-- WARNING: This will delete all existing data!
-- DROP TABLE IF EXISTS document_results;
-- DROP TABLE IF EXISTS processing_sessions;
-- DROP TABLE IF EXISTS clients;

-- Create clients table with new structure
-- If table exists with old structure, this will handle the migration
DO $$
BEGIN
    -- Check if clients table exists
    IF EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'clients') THEN
        -- Add new columns if they don't exist
        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'clients' AND column_name = 'first_name') THEN
            ALTER TABLE clients ADD COLUMN first_name VARCHAR(100);
        END IF;

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'clients' AND column_name = 'last_name') THEN
            ALTER TABLE clients ADD COLUMN last_name VARCHAR(100);
        END IF;

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'clients' AND column_name = 'email') THEN
            ALTER TABLE clients ADD COLUMN email VARCHAR(255);
        END IF;

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'clients' AND column_name = 'phone') THEN
            ALTER TABLE clients ADD COLUMN phone VARCHAR(50);
        END IF;

        -- Migrate existing data if 'name' column exists but first_name/last_name don't have data
        IF EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'clients' AND column_name = 'name') THEN
            UPDATE clients
            SET
                first_name = COALESCE(first_name, SPLIT_PART(name, ' ', 1)),
                last_name = COALESCE(last_name, SUBSTRING(name FROM POSITION(' ' IN name) + 1))
            WHERE first_name IS NULL OR last_name IS NULL;
        END IF;

        -- Make first_name and last_name NOT NULL after migration
        ALTER TABLE clients ALTER COLUMN first_name SET NOT NULL;
        ALTER TABLE clients ALTER COLUMN last_name SET NOT NULL;

        -- Add generated column if it doesn't exist
        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'clients' AND column_name = 'name') THEN
            ALTER TABLE clients ADD COLUMN name VARCHAR(255) GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED;
        END IF;

    ELSE
        -- Create new table
        CREATE TABLE clients (
            id SERIAL PRIMARY KEY,
            first_name VARCHAR(100) NOT NULL,
            last_name VARCHAR(100) NOT NULL,
            name VARCHAR(255) GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED,
            normalized_name VARCHAR(255) NOT NULL DEFAULT '',
            email VARCHAR(255),
            phone VARCHAR(50),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    END IF;
END $$;

-- Create processing_sessions table
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'processing_sessions') THEN
        CREATE TABLE processing_sessions (
            id SERIAL PRIMARY KEY,
            session_id UUID NOT NULL UNIQUE,
            processing_mode VARCHAR(50) NOT NULL DEFAULT 'auto',
            manual_client_info JSONB,
            status VARCHAR(50) NOT NULL DEFAULT 'processing',
            total_files INTEGER DEFAULT 0,
            completed_files INTEGER DEFAULT 0,
            error_files INTEGER DEFAULT 0,
            error_message TEXT,
            started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            completed_at TIMESTAMP WITH TIME ZONE,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    ELSE
        -- Add missing columns to existing table
        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'processing_sessions' AND column_name = 'error_message') THEN
            ALTER TABLE processing_sessions ADD COLUMN error_message TEXT;
        END IF;

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'processing_sessions' AND column_name = 'started_at') THEN
            ALTER TABLE processing_sessions ADD COLUMN started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        END IF;

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'processing_sessions' AND column_name = 'completed_at') THEN
            ALTER TABLE processing_sessions ADD COLUMN completed_at TIMESTAMP WITH TIME ZONE;
        END IF;
    END IF;
END $$;

-- Create document_results table
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'document_results') THEN
        CREATE TABLE document_results (
            id SERIAL PRIMARY KEY,
            session_id INTEGER NOT NULL REFERENCES processing_sessions(id) ON DELETE CASCADE,
            client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
            original_filename VARCHAR(500) NOT NULL,
            new_filename VARCHAR(500),
            document_type VARCHAR(200),
            tax_year INTEGER,
            client_name VARCHAR(255),
            client_folder VARCHAR(255),
            processed_path TEXT,
            status VARCHAR(50) NOT NULL DEFAULT 'processing',
            error_message TEXT,
            confidence DECIMAL(3,2) DEFAULT 0.0,
            processing_time_seconds INTEGER,
            file_size_bytes BIGINT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
    ELSE
        -- Fix existing foreign key if needed
        -- Note: You may need to drop and recreate constraints manually if they exist with wrong references

        -- Add missing columns
        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'document_results' AND column_name = 'processing_time_seconds') THEN
            ALTER TABLE document_results ADD COLUMN processing_time_seconds INTEGER;
        END IF;

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'document_results' AND column_name = 'file_size_bytes') THEN
            ALTER TABLE document_results ADD COLUMN file_size_bytes BIGINT;
        END IF;

        -- Update tax_year to INTEGER if it's currently VARCHAR
        IF EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'document_results' AND column_name = 'tax_year' AND data_type = 'character varying') THEN
            -- Convert VARCHAR tax_year to INTEGER
            ALTER TABLE document_results ADD COLUMN tax_year_int INTEGER;
            UPDATE document_results SET tax_year_int = CASE
                WHEN tax_year ~ '^\d{4}$' THEN tax_year::INTEGER
                ELSE NULL
            END;
            ALTER TABLE document_results DROP COLUMN tax_year;
            ALTER TABLE document_results RENAME COLUMN tax_year_int TO tax_year;
        END IF;
    END IF;
END $$;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_clients_name ON clients(name);
CREATE UNIQUE INDEX IF NOT EXISTS idx_clients_normalized_name ON clients(normalized_name);
CREATE INDEX IF NOT EXISTS idx_clients_first_last ON clients(first_name, last_name);

CREATE INDEX IF NOT EXISTS idx_processing_sessions_session_id ON processing_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_processing_sessions_status ON processing_sessions(status);
CREATE INDEX IF NOT EXISTS idx_processing_sessions_created_at ON processing_sessions(created_at);

CREATE INDEX IF NOT EXISTS idx_document_results_session_id ON document_results(session_id);
CREATE INDEX IF NOT EXISTS idx_document_results_client_id ON document_results(client_id);
CREATE INDEX IF NOT EXISTS idx_document_results_document_type ON document_results(document_type);
CREATE INDEX IF NOT EXISTS idx_document_results_tax_year ON document_results(tax_year);
CREATE INDEX IF NOT EXISTS idx_document_results_status ON document_results(status);
CREATE INDEX IF NOT EXISTS idx_document_results_created_at ON document_results(created_at);
CREATE INDEX IF NOT EXISTS idx_document_results_client_name ON document_results(client_name);

-- Create full-text search index
CREATE INDEX IF NOT EXISTS idx_document_results_filename_search
ON document_results USING gin(to_tsvector('english', original_filename || ' ' || COALESCE(new_filename, '')));

-- Create compound index
CREATE INDEX IF NOT EXISTS idx_document_results_compound
ON document_results(client_id, document_type, tax_year, created_at);

-- Create functions
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE OR REPLACE FUNCTION normalize_client_name(first_name TEXT, last_name TEXT)
RETURNS TEXT AS $$
BEGIN
    RETURN TRIM(LOWER(REGEXP_REPLACE(
        TRIM(first_name) || ' ' || TRIM(last_name), '\s+', ' ', 'g'
    )));
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION set_normalized_client_name()
RETURNS TRIGGER AS $$
BEGIN
    NEW.normalized_name = normalize_client_name(NEW.first_name, NEW.last_name);
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create triggers
CREATE TRIGGER update_clients_updated_at
    BEFORE UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_processing_sessions_updated_at
    BEFORE UPDATE ON processing_sessions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_document_results_updated_at
    BEFORE UPDATE ON document_results
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER set_clients_normalized_name
    BEFORE INSERT OR UPDATE ON clients
    FOR EACH ROW EXECUTE FUNCTION set_normalized_client_name();

-- Create views
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

-- Create search function
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

-- Enable RLS
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_results ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Allow all operations for authenticated users" ON clients
    FOR ALL USING (true);

CREATE POLICY "Allow all operations for authenticated users" ON processing_sessions
    FOR ALL USING (true);

CREATE POLICY "Allow all operations for authenticated users" ON document_results
    FOR ALL USING (true);

-- Grant permissions
GRANT ALL ON clients TO authenticated;
GRANT ALL ON processing_sessions TO authenticated;
GRANT ALL ON document_results TO authenticated;
GRANT ALL ON processing_statistics TO authenticated;
GRANT ALL ON client_statistics TO authenticated;
GRANT ALL ON document_type_statistics TO authenticated;
GRANT ALL ON tax_year_statistics TO authenticated;
GRANT ALL ON recent_activity TO authenticated;

-- Grant sequence usage
GRANT USAGE ON SEQUENCE clients_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE processing_sessions_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE document_results_id_seq TO authenticated;

-- Update normalized_name for existing clients
UPDATE clients SET normalized_name = normalize_client_name(first_name, last_name) WHERE normalized_name = '' OR normalized_name IS NULL;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Database schema migration completed successfully!';
    RAISE NOTICE 'Tables created/updated: clients, processing_sessions, document_results';
    RAISE NOTICE 'Views created: processing_statistics, client_statistics, document_type_statistics, tax_year_statistics, recent_activity';
    RAISE NOTICE 'Functions created: search_documents, normalize_client_name';
END $$;