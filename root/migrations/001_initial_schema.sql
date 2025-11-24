-- QuiboAI Initial Schema Migration
-- Target: Supabase PostgreSQL
-- Created: 2025-11-24

-- Trigger function for automatic updated_at
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 1. Projects table (parent)
CREATE TABLE projects (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name VARCHAR(255) NOT NULL,
  status VARCHAR(50) DEFAULT 'active',
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  archived_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  metadata JSONB DEFAULT '{}'
);

CREATE TRIGGER projects_updated_at
  BEFORE UPDATE ON projects
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 2. Milestones table
CREATE TABLE milestones (
  id SERIAL PRIMARY KEY,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE NOT NULL,
  type VARCHAR(50) NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  data JSONB DEFAULT '{}',
  metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_milestone_project_type ON milestones(project_id, type);

-- 3. Sections table
CREATE TABLE sections (
  id SERIAL PRIMARY KEY,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE NOT NULL,
  section_index INTEGER NOT NULL,
  title VARCHAR(255),
  content TEXT,
  status VARCHAR(50) DEFAULT 'pending',
  cost_delta NUMERIC(12,6) DEFAULT 0,
  input_tokens INTEGER DEFAULT 0,
  output_tokens INTEGER DEFAULT 0,
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(project_id, section_index)
);

CREATE INDEX idx_sections_project ON sections(project_id);

CREATE TRIGGER sections_updated_at
  BEFORE UPDATE ON sections
  FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- 4. Cost tracking table
CREATE TABLE cost_tracking (
  id SERIAL PRIMARY KEY,
  project_id UUID REFERENCES projects(id) ON DELETE CASCADE NOT NULL,
  agent_name VARCHAR(100),
  operation VARCHAR(100),
  model_used VARCHAR(100),
  input_tokens INTEGER DEFAULT 0,
  output_tokens INTEGER DEFAULT 0,
  cost NUMERIC(12,6) DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT now(),
  metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_cost_tracking_project_date ON cost_tracking(project_id, created_at);

-- 5. Completed blogs table
CREATE TABLE completed_blogs (
  id SERIAL PRIMARY KEY,
  project_id UUID REFERENCES projects(id) NOT NULL,
  title VARCHAR(255),
  final_content TEXT,
  word_count INTEGER,
  total_cost NUMERIC(12,6),
  generation_time_seconds INTEGER,
  published_url VARCHAR(500),
  status VARCHAR(50) DEFAULT 'draft',
  version INTEGER DEFAULT 1,
  created_at TIMESTAMPTZ DEFAULT now(),
  published_at TIMESTAMPTZ,
  metadata JSONB DEFAULT '{}'
);

CREATE INDEX idx_completed_blogs_project ON completed_blogs(project_id);
