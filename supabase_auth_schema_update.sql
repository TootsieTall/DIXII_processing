-- Add user_id columns to existing tables for user authentication
-- This script adds user_id columns to support multi-user functionality

-- Add user_id column to clients table
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'clients' AND column_name = 'user_id') THEN
        ALTER TABLE clients ADD COLUMN user_id UUID NOT NULL DEFAULT gen_random_uuid();
        CREATE INDEX IF NOT EXISTS idx_clients_user_id ON clients(user_id);
    END IF;
END $$;

-- Add user_id column to processing_sessions table
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'processing_sessions' AND column_name = 'user_id') THEN
        ALTER TABLE processing_sessions ADD COLUMN user_id UUID NOT NULL DEFAULT gen_random_uuid();
        CREATE INDEX IF NOT EXISTS idx_processing_sessions_user_id ON processing_sessions(user_id);
    END IF;
END $$;

-- Add user_id column to document_results table
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'document_results' AND column_name = 'user_id') THEN
        ALTER TABLE document_results ADD COLUMN user_id UUID NOT NULL DEFAULT gen_random_uuid();
        CREATE INDEX IF NOT EXISTS idx_document_results_user_id ON document_results(user_id);
    END IF;
END $$;

-- Add user_id to enterprise tables as well
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'document_annotations' AND column_name = 'user_id') THEN
        ALTER TABLE document_annotations ADD COLUMN user_id UUID NOT NULL DEFAULT gen_random_uuid();
        CREATE INDEX IF NOT EXISTS idx_document_annotations_user_id ON document_annotations(user_id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'client_profiles' AND column_name = 'user_id') THEN
        ALTER TABLE client_profiles ADD COLUMN user_id UUID NOT NULL DEFAULT gen_random_uuid();
        CREATE INDEX IF NOT EXISTS idx_client_profiles_user_id ON client_profiles(user_id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'client_communications' AND column_name = 'user_id') THEN
        ALTER TABLE client_communications ADD COLUMN user_id UUID NOT NULL DEFAULT gen_random_uuid();
        CREATE INDEX IF NOT EXISTS idx_client_communications_user_id ON client_communications(user_id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'document_versions' AND column_name = 'user_id') THEN
        ALTER TABLE document_versions ADD COLUMN user_id UUID NOT NULL DEFAULT gen_random_uuid();
        CREATE INDEX IF NOT EXISTS idx_document_versions_user_id ON document_versions(user_id);
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'saved_searches' AND column_name = 'user_id') THEN
        -- saved_searches already has user_id as VARCHAR, convert to UUID if needed
        IF EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'saved_searches' AND column_name = 'user_id' AND data_type = 'character varying') THEN
            -- Keep it as VARCHAR for now since it's already used for storing user identifiers
            ALTER TABLE saved_searches ALTER COLUMN user_id TYPE VARCHAR(255);
        END IF;
    END IF;
END $$;

-- Update RLS policies to use user_id filtering
-- Drop existing policies
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON clients;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON processing_sessions;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON document_results;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON document_annotations;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON client_profiles;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON client_communications;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON document_versions;
DROP POLICY IF EXISTS "Allow all operations for authenticated users" ON saved_searches;

-- Create new user-specific policies
CREATE POLICY "Users can manage their own clients" ON clients
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage their own processing sessions" ON processing_sessions
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage their own documents" ON document_results
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage their own annotations" ON document_annotations
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage their own client profiles" ON client_profiles
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage their own communications" ON client_communications
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage their own document versions" ON document_versions
    FOR ALL USING (auth.uid() = user_id);

CREATE POLICY "Users can manage their own saved searches" ON saved_searches
    FOR ALL USING (auth.uid()::text = user_id);

-- Update views to include user_id filtering
CREATE OR REPLACE VIEW client_statistics AS
SELECT
    c.id,
    c.user_id,
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
LEFT JOIN document_results dr ON c.id = dr.client_id AND c.user_id = dr.user_id
GROUP BY c.id, c.user_id, c.first_name, c.last_name, c.name, c.email, c.phone, c.created_at
ORDER BY total_documents DESC;

CREATE OR REPLACE VIEW client_dashboard_data AS
SELECT
    c.id,
    c.user_id,
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
LEFT JOIN client_profiles cp ON c.id = cp.client_id AND c.user_id = cp.user_id
LEFT JOIN document_results dr ON c.id = dr.client_id AND c.user_id = dr.user_id
LEFT JOIN client_communications cc ON c.id = cc.client_id AND c.user_id = cc.user_id
GROUP BY c.id, c.user_id, c.first_name, c.last_name, c.name, c.email, c.phone,
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
LEFT JOIN clients c ON dr.client_id = c.id AND dr.user_id = c.user_id
LEFT JOIN client_profiles cp ON c.id = cp.client_id AND c.user_id = cp.user_id
LEFT JOIN document_annotations da ON dr.id = da.document_id AND dr.user_id = da.user_id
LEFT JOIN document_versions dv ON dr.id = dv.document_id AND dr.user_id = dv.user_id
GROUP BY dr.id, dr.user_id, dr.session_id, dr.client_id, dr.original_filename,
         dr.new_filename, dr.document_type, dr.tax_year, dr.client_name,
         dr.client_folder, dr.processed_path, dr.status, dr.confidence,
         dr.error_message, dr.processing_time_seconds, dr.file_size_bytes,
         dr.created_at, dr.updated_at, c.name, cp.business_type;

-- Update the advanced search function to include user_id filtering
CREATE OR REPLACE FUNCTION advanced_document_search(
    search_user_id UUID,
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
        LEFT JOIN clients c ON dr.client_id = c.id AND dr.user_id = c.user_id
        LEFT JOIN client_profiles cp ON c.id = cp.client_id AND c.user_id = cp.user_id
        LEFT JOIN document_annotations da ON dr.id = da.document_id AND dr.user_id = da.user_id
        WHERE
            dr.user_id = $1
            AND ($2 = '''' OR
                 dr.original_filename ILIKE ''%%'' || $2 || ''%%'' OR
                 dr.new_filename ILIKE ''%%'' || $2 || ''%%'' OR
                 dr.client_name ILIKE ''%%'' || $2 || ''%%'' OR
                 dr.document_type ILIKE ''%%'' || $2 || ''%%'')
            AND ($3 IS NULL OR dr.client_id = $3)
            AND ($4 IS NULL OR dr.document_type = $4)
            AND ($5 IS NULL OR dr.tax_year = $5)
            AND ($6 IS NULL OR dr.status = $6)
            AND ($7 IS NULL OR dr.created_at::date >= $7)
            AND ($8 IS NULL OR dr.created_at::date <= $8)
            AND ($9 IS NULL OR ($9 = true AND da.id IS NOT NULL) OR ($9 = false AND da.id IS NULL))
            AND ($10 IS NULL OR dr.confidence >= $10)
        GROUP BY dr.id, c.name, cp.business_type
        ORDER BY %s
        LIMIT $11 OFFSET $12
    ', sort_clause)
    USING search_user_id, search_query, client_id_filter, document_type_filter, tax_year_filter,
          status_filter, date_from, date_to, has_annotations, confidence_min,
          limit_count, offset_count;
END;
$$ LANGUAGE plpgsql;

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'User authentication schema update completed successfully!';
    RAISE NOTICE 'Added user_id columns to all relevant tables';
    RAISE NOTICE 'Updated RLS policies for user-specific data access';
    RAISE NOTICE 'Updated views and functions to filter by user_id';
    RAISE NOTICE 'Now ready for multi-user authentication!';
END $$;