-- Migration: Create outline feedback tables for version tracking
-- This migration adds tables to support outline regeneration with feedback

-- Create outline_versions table first (without feedback reference)
CREATE TABLE IF NOT EXISTS outline_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version_number INTEGER NOT NULL,
    outline_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    -- feedback_id will be added later
    UNIQUE(project_id, version_number)
);

-- Create outline_feedback table
CREATE TABLE IF NOT EXISTS outline_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    outline_version_id UUID REFERENCES outline_versions(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    focus_area VARCHAR(50) CHECK (focus_area IN ('Structure', 'Content Depth', 'Flow', 'Technical Level')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    source VARCHAR(20) DEFAULT 'user' CHECK (source IN ('user', 'auto'))
);

-- Add feedback_id column to outline_versions (after both tables exist)
ALTER TABLE outline_versions
ADD COLUMN IF NOT EXISTS feedback_id UUID REFERENCES outline_feedback(id) ON DELETE SET NULL;

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_outline_versions_project_id ON outline_versions(project_id);
CREATE INDEX IF NOT EXISTS idx_outline_versions_created_at ON outline_versions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_outline_feedback_version_id ON outline_feedback(outline_version_id);

-- Add comment documentation
COMMENT ON TABLE outline_versions IS 'Stores different versions of blog outlines with version tracking';
COMMENT ON TABLE outline_feedback IS 'Stores user feedback for outline regeneration';
COMMENT ON COLUMN outline_versions.version_number IS 'Sequential version number (1, 2, 3, etc.)';
COMMENT ON COLUMN outline_versions.feedback_id IS 'Links to the feedback that generated this version';
COMMENT ON COLUMN outline_feedback.focus_area IS 'Area of focus for the feedback (Structure, Content Depth, Flow, Technical Level)';

-- Migration completed successfully
SELECT 'Outline feedback tables created successfully' as migration_status;