-- Supabase Database Schema for Tax Document Processing Application
-- Migration-Safe Version with Proper Dependency Handling
-- This script will work whether you have existing tables or not

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Drop existing policies first
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON clients;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON processing_sessions;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON document_results;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON document_annotations;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON client_profiles;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON document_relationships;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON client_communications;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON document_versions;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON saved_searches;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON processing_analytics;

-- Drop all triggers first (to avoid dependency issues)
DROP TRIGGER IF EXISTS set_clients_normalized_name ON clients;
DROP TRIGGER IF EXISTS update_clients_updated_at ON clients;
DROP TRIGGER IF EXISTS update_processing_sessions_updated_at ON processing_sessions;
DROP TRIGGER IF EXISTS update_document_results_updated_at ON document_results;
DROP TRIGGER IF EXISTS update_document_annotations_updated_at ON document_annotations;
DROP TRIGGER IF EXISTS update_client_profiles_updated_at ON client_profiles;
DROP TRIGGER IF EXISTS update_saved_searches_updated_at ON saved_searches;

-- Now drop functions (after triggers are removed)
DROP FUNCTION IF EXISTS set_normalized_client_name();
DROP FUNCTION IF EXISTS normalize_client_name(TEXT, TEXT);
DROP FUNCTION IF EXISTS normalize_client_name(TEXT);
DROP FUNCTION IF EXISTS update_updated_at_column();
DROP FUNCTION IF EXISTS search_documents(TEXT, INTEGER, TEXT, INTEGER, INTEGER);
DROP FUNCTION IF EXISTS advanced_document_search(TEXT, INTEGER, TEXT, INTEGER, TEXT, DATE, DATE, BOOLEAN, DECIMAL, TEXT, TEXT, INTEGER, INTEGER);

-- Drop existing views
DROP VIEW IF EXISTS recent_activity_enhanced;
DROP VIEW IF EXISTS document_type_analytics;
DROP VIEW IF EXISTS documents_with_annotations;
DROP VIEW IF EXISTS client_dashboard_data;
DROP VIEW IF EXISTS recent_activity;
DROP VIEW IF EXISTS tax_year_statistics;
DROP VIEW IF EXISTS document_type_statistics;
DROP VIEW IF EXISTS client_statistics;
DROP VIEW IF EXISTS processing_statistics;

-- For fresh install or if you want to recreate tables, uncomment these lines:
-- WARNING: This will delete all existing data!
-- DROP TABLE IF EXISTS document_annotations CASCADE;
-- DROP TABLE IF EXISTS client_profiles CASCADE;
-- DROP TABLE IF EXISTS document_relationships CASCADE;
-- DROP TABLE IF EXISTS client_communications CASCADE;
-- DROP TABLE IF EXISTS document_versions CASCADE;
-- DROP TABLE IF EXISTS saved_searches CASCADE;
-- DROP TABLE IF EXISTS processing_analytics CASCADE;
-- DROP TABLE IF EXISTS document_results CASCADE;
-- DROP TABLE IF EXISTS processing_sessions CASCADE;
-- DROP TABLE IF EXISTS clients CASCADE;

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

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'clients' AND column_name = 'normalized_name') THEN
            ALTER TABLE clients ADD COLUMN normalized_name VARCHAR(255) DEFAULT '';
        END IF;

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'clients' AND column_name = 'created_at') THEN
            ALTER TABLE clients ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        END IF;

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'clients' AND column_name = 'updated_at') THEN
            ALTER TABLE clients ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        END IF;

        -- Migrate existing data if 'name' column exists but first_name/last_name don't have data
        IF EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'clients' AND column_name = 'name') THEN
            UPDATE clients
            SET
                first_name = COALESCE(first_name, SPLIT_PART(name, ' ', 1)),
                last_name = COALESCE(last_name, SUBSTRING(name FROM POSITION(' ' IN name) + 1))
            WHERE first_name IS NULL OR last_name IS NULL OR first_name = '' OR last_name = '';
        END IF;

        -- Make first_name and last_name NOT NULL after migration
        UPDATE clients SET first_name = 'Unknown' WHERE first_name IS NULL OR first_name = '';
        UPDATE clients SET last_name = 'Client' WHERE last_name IS NULL OR last_name = '';
        ALTER TABLE clients ALTER COLUMN first_name SET NOT NULL;
        ALTER TABLE clients ALTER COLUMN last_name SET NOT NULL;

        -- Drop and recreate the generated name column if it exists
        IF EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'clients' AND column_name = 'name') THEN
            ALTER TABLE clients DROP COLUMN IF EXISTS name;
        END IF;
        ALTER TABLE clients ADD COLUMN name VARCHAR(255) GENERATED ALWAYS AS (first_name || ' ' || last_name) STORED;

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

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'processing_sessions' AND column_name = 'created_at') THEN
            ALTER TABLE processing_sessions ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        END IF;

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'processing_sessions' AND column_name = 'updated_at') THEN
            ALTER TABLE processing_sessions ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
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
        -- Add missing columns
        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'document_results' AND column_name = 'processing_time_seconds') THEN
            ALTER TABLE document_results ADD COLUMN processing_time_seconds INTEGER;
        END IF;

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'document_results' AND column_name = 'file_size_bytes') THEN
            ALTER TABLE document_results ADD COLUMN file_size_bytes BIGINT;
        END IF;

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'document_results' AND column_name = 'created_at') THEN
            ALTER TABLE document_results ADD COLUMN created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
        END IF;

        IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'document_results' AND column_name = 'updated_at') THEN
            ALTER TABLE document_results ADD COLUMN updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW();
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

-- Create enterprise tables
CREATE TABLE IF NOT EXISTS document_annotations (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES document_results(id) ON DELETE CASCADE,
    annotation_type VARCHAR(50) NOT NULL DEFAULT 'note',
    content TEXT NOT NULL,
    position_data JSONB,
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS client_profiles (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE UNIQUE,
    business_type VARCHAR(100),
    tax_id VARCHAR(50),
    preferred_contact VARCHAR(20) DEFAULT 'email',
    filing_frequency VARCHAR(20) DEFAULT 'annual',
    portal_access BOOLEAN DEFAULT FALSE,
    compliance_status VARCHAR(50) DEFAULT 'current',
    notes TEXT,
    communication_preferences JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_relationships (
    id SERIAL PRIMARY KEY,
    parent_document_id INTEGER REFERENCES document_results(id) ON DELETE CASCADE,
    child_document_id INTEGER REFERENCES document_results(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(parent_document_id, child_document_id, relationship_type)
);

CREATE TABLE IF NOT EXISTS client_communications (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    communication_type VARCHAR(50) NOT NULL,
    subject VARCHAR(255),
    content TEXT,
    communication_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS document_versions (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES document_results(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL DEFAULT 1,
    file_path TEXT,
    file_size_bytes BIGINT,
    upload_reason VARCHAR(255),
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS saved_searches (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255),
    search_name VARCHAR(255) NOT NULL,
    search_criteria JSONB NOT NULL,
    is_shared BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS processing_analytics (
    id SERIAL PRIMARY KEY,
    processing_date DATE NOT NULL,
    total_documents INTEGER DEFAULT 0,
    successful_documents INTEGER DEFAULT 0,
    failed_documents INTEGER DEFAULT 0,
    avg_processing_time_seconds DECIMAL(10,2),
    total_file_size_mb DECIMAL(12,2),
    unique_clients INTEGER DEFAULT 0,
    document_types_processed JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

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

CREATE INDEX IF NOT EXISTS idx_document_results_filename_search
ON document_results USING gin(to_tsvector('english', original_filename || ' ' || COALESCE(new_filename, '')));

CREATE INDEX IF NOT EXISTS idx_document_results_compound
ON document_results(client_id, document_type, tax_year, created_at);

-- Enterprise table indexes
CREATE INDEX IF NOT EXISTS idx_document_annotations_document_id ON document_annotations(document_id);
CREATE INDEX IF NOT EXISTS idx_document_annotations_type ON document_annotations(annotation_type);
CREATE INDEX IF NOT EXISTS idx_client_profiles_client_id ON client_profiles(client_id);
CREATE INDEX IF NOT EXISTS idx_client_profiles_business_type ON client_profiles(business_type);
CREATE INDEX IF NOT EXISTS idx_document_relationships_parent ON document_relationships(parent_document_id);
CREATE INDEX IF NOT EXISTS idx_document_relationships_child ON document_relationships(child_document_id);
CREATE INDEX IF NOT EXISTS idx_client_communications_client_id ON client_communications(client_id);
CREATE INDEX IF NOT EXISTS idx_client_communications_date ON client_communications(communication_date);
CREATE INDEX IF NOT EXISTS idx_document_versions_document_id ON document_versions(document_id);
CREATE INDEX IF NOT EXISTS idx_saved_searches_user_id ON saved_searches(user_id);
CREATE INDEX IF NOT EXISTS idx_processing_analytics_date ON processing_analytics(processing_date);

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

-- Enhanced search function
CREATE OR REPLACE FUNCTION advanced_document_search(
    search_query TEXT DEFAULT '',
    client_id_filter INTEGER DEFAULT NULL,
    document_type_filter TEXT DEFAULT NULL,
    tax_year_filter INTEGER DEFAULT NULL,
    status_filter TEXT DEFAULT NULL,
    date_from DATE DEFAULT NULL,
    date_to DATE DEFAULT NULL,
    has_annotations BOOLEAN DEFAULT NULL,
    confidence_min DECIMAL DEFAULT NULL,
    sort_by TEXT DEFAULT 'created_at',
    sort_order TEXT DEFAULT 'DESC',
    limit_count INTEGER DEFAULT 50,
    offset_count INTEGER DEFAULT 0
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
    file_size_bytes BIGINT,
    annotation_count BIGINT,
    created_at TIMESTAMP WITH TIME ZONE,
    client_full_name TEXT,
    business_type VARCHAR(100)
) AS $$
DECLARE
    sort_clause TEXT;
BEGIN
    -- Build dynamic sort clause
    sort_clause := CASE sort_by
        WHEN 'filename' THEN 'dr.original_filename'
        WHEN 'client' THEN 'dr.client_name'
        WHEN 'type' THEN 'dr.document_type'
        WHEN 'size' THEN 'dr.file_size_bytes'
        WHEN 'confidence' THEN 'dr.confidence'
        ELSE 'dr.created_at'
    END || ' ' || sort_order;

    RETURN QUERY EXECUTE format('
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
            dr.file_size_bytes,
            COUNT(da.id) as annotation_count,
            dr.created_at,
            c.name as client_full_name,
            cp.business_type
        FROM document_results dr
        LEFT JOIN clients c ON dr.client_id = c.id
        LEFT JOIN client_profiles cp ON c.id = cp.client_id
        LEFT JOIN document_annotations da ON dr.id = da.document_id
        WHERE
            ($1 = '''' OR
             dr.original_filename ILIKE ''%%'' || $1 || ''%%'' OR
             dr.new_filename ILIKE ''%%'' || $1 || ''%%'' OR
             dr.client_name ILIKE ''%%'' || $1 || ''%%'' OR
             dr.document_type ILIKE ''%%'' || $1 || ''%%'')
            AND ($2 IS NULL OR dr.client_id = $2)
            AND ($3 IS NULL OR dr.document_type = $3)
            AND ($4 IS NULL OR dr.tax_year = $4)
            AND ($5 IS NULL OR dr.status = $5)
            AND ($6 IS NULL OR dr.created_at::date >= $6)
            AND ($7 IS NULL OR dr.created_at::date <= $7)
            AND ($8 IS NULL OR ($8 = true AND da.id IS NOT NULL) OR ($8 = false AND da.id IS NULL))
            AND ($9 IS NULL OR dr.confidence >= $9)
        GROUP BY dr.id, c.name, cp.business_type
        ORDER BY %s
        LIMIT $10 OFFSET $11
    ', sort_clause)
    USING search_query, client_id_filter, document_type_filter, tax_year_filter,
          status_filter, date_from, date_to, has_annotations, confidence_min,
          limit_count, offset_count;
END;
$$ LANGUAGE plpgsql;

-- Basic search function for backward compatibility
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

-- Create triggers (after functions are created)
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

CREATE TRIGGER update_document_annotations_updated_at
    BEFORE UPDATE ON document_annotations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_client_profiles_updated_at
    BEFORE UPDATE ON client_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_saved_searches_updated_at
    BEFORE UPDATE ON saved_searches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

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

-- Enterprise views
CREATE OR REPLACE VIEW client_dashboard_data AS
SELECT
    c.id,
    c.first_name,
    c.last_name,
    c.name,
    c.email,
    c.phone,
    cp.business_type,
    cp.tax_id,
    cp.preferred_contact,
    cp.filing_frequency,
    cp.compliance_status,
    cp.portal_access,
    cp.notes as profile_notes,
    COUNT(DISTINCT dr.id) as total_documents,
    COUNT(DISTINCT CASE WHEN dr.status = 'completed' THEN dr.id END) as completed_documents,
    COUNT(DISTINCT CASE WHEN dr.status = 'error' THEN dr.id END) as error_documents,
    COUNT(DISTINCT dr.tax_year) as unique_tax_years,
    MAX(dr.created_at) as last_document_date,
    COUNT(DISTINCT cc.id) as communication_count,
    MAX(cc.communication_date) as last_communication_date
FROM clients c
LEFT JOIN client_profiles cp ON c.id = cp.client_id
LEFT JOIN document_results dr ON c.id = dr.client_id
LEFT JOIN client_communications cc ON c.id = cc.client_id
GROUP BY c.id, c.first_name, c.last_name, c.name, c.email, c.phone,
         cp.business_type, cp.tax_id, cp.preferred_contact, cp.filing_frequency,
         cp.compliance_status, cp.portal_access, cp.notes;

CREATE OR REPLACE VIEW documents_with_annotations AS
SELECT
    dr.*,
    c.name as client_full_name,
    cp.business_type,
    COUNT(da.id) as annotation_count,
    COUNT(dv.id) as version_count,
    MAX(da.created_at) as last_annotation_date
FROM document_results dr
LEFT JOIN clients c ON dr.client_id = c.id
LEFT JOIN client_profiles cp ON c.id = cp.client_id
LEFT JOIN document_annotations da ON dr.id = da.document_id
LEFT JOIN document_versions dv ON dr.id = dv.document_id
GROUP BY dr.id, c.name, cp.business_type;

CREATE OR REPLACE VIEW recent_activity_enhanced AS
SELECT
    'document_upload' as activity_type,
    dr.id,
    dr.original_filename as description,
    dr.client_name,
    dr.document_type,
    dr.status,
    dr.created_at
FROM document_results dr
WHERE dr.created_at >= NOW() - INTERVAL '30 days'

UNION ALL

SELECT
    'annotation' as activity_type,
    da.id,
    'Annotation: ' || LEFT(da.content, 50) || '...' as description,
    c.name as client_name,
    da.annotation_type as document_type,
    'completed' as status,
    da.created_at
FROM document_annotations da
JOIN document_results dr ON da.document_id = dr.id
JOIN clients c ON dr.client_id = c.id
WHERE da.created_at >= NOW() - INTERVAL '30 days'

UNION ALL

SELECT
    'communication' as activity_type,
    cc.id,
    cc.subject as description,
    c.name as client_name,
    cc.communication_type as document_type,
    'completed' as status,
    cc.communication_date as created_at
FROM client_communications cc
JOIN clients c ON cc.client_id = c.id
WHERE cc.communication_date >= NOW() - INTERVAL '30 days'

ORDER BY created_at DESC
LIMIT 50;

-- Enable RLS
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_results ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_annotations ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_communications ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_analytics ENABLE ROW LEVEL SECURITY;

-- Create policies
CREATE POLICY "Allow all operations for authenticated users" ON clients FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON processing_sessions FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON document_results FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON document_annotations FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON client_profiles FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON document_relationships FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON client_communications FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON document_versions FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON saved_searches FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON processing_analytics FOR ALL USING (true);

-- Grant permissions
GRANT ALL ON clients TO authenticated;
GRANT ALL ON processing_sessions TO authenticated;
GRANT ALL ON document_results TO authenticated;
GRANT ALL ON document_annotations TO authenticated;
GRANT ALL ON client_profiles TO authenticated;
GRANT ALL ON document_relationships TO authenticated;
GRANT ALL ON client_communications TO authenticated;
GRANT ALL ON document_versions TO authenticated;
GRANT ALL ON saved_searches TO authenticated;
GRANT ALL ON processing_analytics TO authenticated;

-- Grant permissions on views
GRANT ALL ON processing_statistics TO authenticated;
GRANT ALL ON client_statistics TO authenticated;
GRANT ALL ON document_type_statistics TO authenticated;
GRANT ALL ON tax_year_statistics TO authenticated;
GRANT ALL ON recent_activity TO authenticated;
GRANT ALL ON client_dashboard_data TO authenticated;
GRANT ALL ON documents_with_annotations TO authenticated;
GRANT ALL ON recent_activity_enhanced TO authenticated;

-- Grant sequence usage
GRANT USAGE ON SEQUENCE clients_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE processing_sessions_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE document_results_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE document_annotations_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE client_profiles_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE document_relationships_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE client_communications_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE document_versions_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE saved_searches_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE processing_analytics_id_seq TO authenticated;

-- Update normalized_name for existing clients
UPDATE clients SET normalized_name = normalize_client_name(first_name, last_name) WHERE normalized_name = '' OR normalized_name IS NULL;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'Database schema migration completed successfully!';
    RAISE NOTICE 'Tables created/updated: clients, processing_sessions, document_results';
    RAISE NOTICE 'Enterprise tables created: document_annotations, client_profiles, document_relationships, client_communications, document_versions, saved_searches, processing_analytics';
    RAISE NOTICE 'Views created: processing_statistics, client_statistics, document_type_statistics, tax_year_statistics, recent_activity, client_dashboard_data, documents_with_annotations, recent_activity_enhanced';
    RAISE NOTICE 'Functions created: search_documents, advanced_document_search, normalize_client_name';
    RAISE NOTICE 'Enterprise document management system is ready!';
END $$;