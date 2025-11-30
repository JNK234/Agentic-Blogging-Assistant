-- ABOUTME: Migration to add outline version tracking to sections table
-- ABOUTME: Enables detection of section/outline mismatch after outline modifications

-- Add outline_hash column to sections table
-- This stores the full SHA256 hash of the outline when each section was generated
-- Used to detect when sections were generated with a different outline version
ALTER TABLE sections
ADD COLUMN IF NOT EXISTS outline_hash VARCHAR(64);

-- Add comment for documentation
COMMENT ON COLUMN sections.outline_hash IS
  'Full SHA256 hash (64 chars) of outline when section was generated, for detecting outline/section drift';

-- Index for efficient querying of sections by outline version
CREATE INDEX IF NOT EXISTS idx_sections_outline_hash
ON sections(project_id, outline_hash);

-- Log migration completion
DO $$
BEGIN
  RAISE NOTICE 'Migration 002: Added outline_hash column to sections table';
  RAISE NOTICE 'Existing sections without outline_hash: %',
    (SELECT COUNT(*) FROM sections WHERE outline_hash IS NULL);
END $$;
