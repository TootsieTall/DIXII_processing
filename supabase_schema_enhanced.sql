-- Enhanced Supabase Database Schema for Enterprise Document Management
-- This file contains the new tables and enhancements for the enterprise features
-- Run after the base supabase_schema.sql

-- Document annotations and notes
CREATE TABLE IF NOT EXISTS document_annotations (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES document_results(id) ON DELETE CASCADE,
    annotation_type VARCHAR(50) NOT NULL DEFAULT 'note', -- 'note', 'highlight', 'approval', 'flag'
    content TEXT NOT NULL,
    position_data JSONB, -- For highlight coordinates, page numbers, etc.
    created_by VARCHAR(255), -- User who created the annotation
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Enhanced client profiles
CREATE TABLE IF NOT EXISTS client_profiles (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE UNIQUE,
    business_type VARCHAR(100), -- 'individual', 'partnership', 'corporation', 'llc', etc.
    tax_id VARCHAR(50), -- EIN or SSN
    preferred_contact VARCHAR(20) DEFAULT 'email', -- 'email', 'phone', 'mail'
    filing_frequency VARCHAR(20) DEFAULT 'annual', -- 'annual', 'quarterly', 'monthly'
    portal_access BOOLEAN DEFAULT FALSE,
    compliance_status VARCHAR(50) DEFAULT 'current', -- 'current', 'pending', 'overdue'
    notes TEXT,
    communication_preferences JSONB, -- Email notifications, etc.
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document relationships (linked documents)
CREATE TABLE IF NOT EXISTS document_relationships (
    id SERIAL PRIMARY KEY,
    parent_document_id INTEGER REFERENCES document_results(id) ON DELETE CASCADE,
    child_document_id INTEGER REFERENCES document_results(id) ON DELETE CASCADE,
    relationship_type VARCHAR(50) NOT NULL, -- 'supporting', 'revision', 'related', 'superseded'
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(parent_document_id, child_document_id, relationship_type)
);

-- Client communication log
CREATE TABLE IF NOT EXISTS client_communications (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    communication_type VARCHAR(50) NOT NULL, -- 'call', 'email', 'meeting', 'note'
    subject VARCHAR(255),
    content TEXT,
    communication_date TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document version history
CREATE TABLE IF NOT EXISTS document_versions (
    id SERIAL PRIMARY KEY,
    document_id INTEGER REFERENCES document_results(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL DEFAULT 1,
    file_path TEXT,
    file_size_bytes BIGINT,
    upload_reason VARCHAR(255), -- 'correction', 'update', 'reprocessing'
    created_by VARCHAR(255),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Saved search queries
CREATE TABLE IF NOT EXISTS saved_searches (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(255), -- Will be used when user authentication is implemented
    search_name VARCHAR(255) NOT NULL,
    search_criteria JSONB NOT NULL, -- Store complete search parameters
    is_shared BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Document processing analytics (for enhanced reporting)
CREATE TABLE IF NOT EXISTS processing_analytics (
    id SERIAL PRIMARY KEY,
    processing_date DATE NOT NULL,
    total_documents INTEGER DEFAULT 0,
    successful_documents INTEGER DEFAULT 0,
    failed_documents INTEGER DEFAULT 0,
    avg_processing_time_seconds DECIMAL(10,2),
    total_file_size_mb DECIMAL(12,2),
    unique_clients INTEGER DEFAULT 0,
    document_types_processed JSONB, -- Count by document type
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better performance
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

-- Enhanced views for the enterprise features

-- Comprehensive client dashboard view
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

-- Enhanced document search view with annotations
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

-- Document type analytics view
CREATE OR REPLACE VIEW document_type_analytics AS
SELECT
    document_type,
    COUNT(*) as total_documents,
    COUNT(CASE WHEN status = 'completed' THEN 1 END) as completed_documents,
    COUNT(CASE WHEN status = 'error' THEN 1 END) as error_documents,
    ROUND(AVG(confidence), 4) as avg_confidence,
    COUNT(DISTINCT client_id) as unique_clients,
    COUNT(DISTINCT tax_year) as unique_tax_years,
    MIN(created_at) as first_processed,
    MAX(created_at) as last_processed,
    SUM(file_size_bytes) as total_file_size
FROM document_results
WHERE document_type IS NOT NULL
GROUP BY document_type
ORDER BY total_documents DESC;

-- Recent activity with more details
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

-- Add triggers for updated_at timestamps
CREATE TRIGGER update_document_annotations_updated_at
    BEFORE UPDATE ON document_annotations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_client_profiles_updated_at
    BEFORE UPDATE ON client_profiles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_saved_searches_updated_at
    BEFORE UPDATE ON saved_searches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Enhanced search function with multiple filters
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

-- Enable RLS on new tables
ALTER TABLE document_annotations ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_relationships ENABLE ROW LEVEL SECURITY;
ALTER TABLE client_communications ENABLE ROW LEVEL SECURITY;
ALTER TABLE document_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE saved_searches ENABLE ROW LEVEL SECURITY;
ALTER TABLE processing_analytics ENABLE ROW LEVEL SECURITY;

-- Create policies for new tables
CREATE POLICY "Allow all operations for authenticated users" ON document_annotations FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON client_profiles FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON document_relationships FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON client_communications FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON document_versions FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON saved_searches FOR ALL USING (true);
CREATE POLICY "Allow all operations for authenticated users" ON processing_analytics FOR ALL USING (true);

-- Grant permissions on new tables
GRANT ALL ON document_annotations TO authenticated;
GRANT ALL ON client_profiles TO authenticated;
GRANT ALL ON document_relationships TO authenticated;
GRANT ALL ON client_communications TO authenticated;
GRANT ALL ON document_versions TO authenticated;
GRANT ALL ON saved_searches TO authenticated;
GRANT ALL ON processing_analytics TO authenticated;

-- Grant permissions on new views
GRANT ALL ON client_dashboard_data TO authenticated;
GRANT ALL ON documents_with_annotations TO authenticated;
GRANT ALL ON document_type_analytics TO authenticated;
GRANT ALL ON recent_activity_enhanced TO authenticated;

-- Grant usage on new sequences
GRANT USAGE ON SEQUENCE document_annotations_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE client_profiles_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE document_relationships_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE client_communications_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE document_versions_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE saved_searches_id_seq TO authenticated;
GRANT USAGE ON SEQUENCE processing_analytics_id_seq TO authenticated;