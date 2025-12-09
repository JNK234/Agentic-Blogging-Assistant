-- ABOUTME: Migration to add image placeholder storage to sections table
-- ABOUTME: Enables persistence of AI-generated image suggestions for blog sections

-- Add image_placeholders column as JSONB for flexible structured data
ALTER TABLE sections
ADD COLUMN IF NOT EXISTS image_placeholders JSONB DEFAULT '[]'::jsonb;

-- Add comment for documentation
COMMENT ON COLUMN sections.image_placeholders IS
  'Array of ImagePlaceholder objects: [{type, description, alt_text, placement, purpose, section_context, source_reference}]';

-- Create GIN index for efficient JSONB queries
CREATE INDEX IF NOT EXISTS idx_sections_image_placeholders
ON sections USING GIN (image_placeholders);
