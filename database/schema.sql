-- Idea Engine App Database Schema
-- PostgreSQL Database for n8n Workflow System

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Ideas table: Stores all generated ideas
CREATE TABLE IF NOT EXISTS ideas (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(255) NOT NULL,
    description TEXT,
    category VARCHAR(100),
    source VARCHAR(100), -- 'reddit', 'twitter', 'trends', 'ai_generated', etc.
    market_size_estimate DECIMAL(15,2),
    validation_score DECIMAL(5,2),
    status VARCHAR(50) DEFAULT 'pending', -- pending, validating, validated, selected, rejected, archived
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Validation results table
CREATE TABLE IF NOT EXISTS validation_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idea_id UUID REFERENCES ideas(id) ON DELETE CASCADE,
    metric_name VARCHAR(100),
    metric_value DECIMAL(10,2),
    raw_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Projects table: Ideas that have been selected for implementation
CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    idea_id UUID REFERENCES ideas(id),
    project_name VARCHAR(255) NOT NULL,
    project_slug VARCHAR(100) UNIQUE NOT NULL,
    website_url VARCHAR(500),
    github_repo VARCHAR(500),
    status VARCHAR(50) DEFAULT 'initializing', -- initializing, active, paused, scaled, exited
    launch_date TIMESTAMP,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Social accounts table
CREATE TABLE IF NOT EXISTS social_accounts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    platform VARCHAR(50), -- twitter, linkedin, instagram, tiktok
    username VARCHAR(100),
    profile_url VARCHAR(500),
    follower_count INTEGER DEFAULT 0,
    engagement_rate DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Content calendar table
CREATE TABLE IF NOT EXISTS content_calendar (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    platform VARCHAR(50),
    content_type VARCHAR(50), -- post, story, reel, thread
    content TEXT,
    media_urls TEXT[],
    scheduled_for TIMESTAMP,
    published_at TIMESTAMP,
    performance_metrics JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'scheduled', -- scheduled, published, failed
    created_at TIMESTAMP DEFAULT NOW()
);

-- Analytics table
CREATE TABLE IF NOT EXISTS analytics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    project_id UUID REFERENCES projects(id) ON DELETE CASCADE,
    metric_type VARCHAR(100), -- website_visitors, conversions, social_engagement, etc.
    metric_value DECIMAL(15,2),
    metric_date DATE,
    dimensions JSONB DEFAULT '{}', -- Additional breakdown data
    created_at TIMESTAMP DEFAULT NOW()
);

-- Workflow runs table (for tracking n8n executions)
CREATE TABLE IF NOT EXISTS workflow_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workflow_name VARCHAR(255),
    workflow_id VARCHAR(100),
    project_id UUID REFERENCES projects(id),
    status VARCHAR(50), -- running, success, failed
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    error_message TEXT,
    metadata JSONB DEFAULT '{}'
);

-- Decision log table (for AI decisions and scoring)
CREATE TABLE IF NOT EXISTS decision_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    entity_type VARCHAR(50), -- idea, project
    entity_id UUID,
    decision_type VARCHAR(100), -- validation, selection, scaling, exit
    decision_result VARCHAR(100),
    reasoning TEXT,
    score DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_ideas_status ON ideas(status);
CREATE INDEX idx_ideas_created_at ON ideas(created_at DESC);
CREATE INDEX idx_projects_status ON projects(status);
CREATE INDEX idx_analytics_project_date ON analytics(project_id, metric_date DESC);
CREATE INDEX idx_content_calendar_scheduled ON content_calendar(scheduled_for);
CREATE INDEX idx_workflow_runs_status ON workflow_runs(status, started_at DESC);

-- Triggers for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_ideas_updated_at BEFORE UPDATE ON ideas
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_projects_updated_at BEFORE UPDATE ON projects
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_social_accounts_updated_at BEFORE UPDATE ON social_accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
