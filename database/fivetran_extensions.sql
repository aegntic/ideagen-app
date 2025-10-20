-- Fivetran Connector Extensions for IdeaGen Database
-- Schema extensions for data sources: Reddit, Product Hunt, Google Trends, Twitter/X

-- =============================================================================
-- REDDIT DATA SCHEMA
-- =============================================================================

-- Reddit posts table (enhanced from basic ideas table)
CREATE TABLE IF NOT EXISTS reddit_posts (
    id VARCHAR(20) PRIMARY KEY,  -- Reddit post ID
    title VARCHAR(500) NOT NULL,
    author VARCHAR(100),
    subreddit VARCHAR(100) NOT NULL,
    score INTEGER DEFAULT 0,
    upvote_ratio DECIMAL(3,2) DEFAULT 0.0,
    num_comments INTEGER DEFAULT 0,
    created_utc TIMESTAMP,
    permalink VARCHAR(1000),
    url VARCHAR(1000),
    selftext TEXT,
    post_hint VARCHAR(50),
    domain VARCHAR(255),
    flair_text VARCHAR(200),
    is_self BOOLEAN DEFAULT FALSE,
    over_18 BOOLEAN DEFAULT FALSE,
    awards INTEGER DEFAULT 0,
    media_metadata JSONB DEFAULT '{}',
    extracted_entities JSONB DEFAULT '{}',
    idea_signals JSONB DEFAULT '{}',
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT reddit_posts_check_score CHECK (score >= 0),
    CONSTRAINT reddit_posts_check_ratio CHECK (upvote_ratio >= 0 AND upvote_ratio <= 1),
    CONSTRAINT reddit_posts_check_comments CHECK (num_comments >= 0)
);

-- Reddit comments table
CREATE TABLE IF NOT EXISTS reddit_comments (
    id VARCHAR(20) PRIMARY KEY,  -- Reddit comment ID
    post_id VARCHAR(20) NOT NULL REFERENCES reddit_posts(id) ON DELETE CASCADE,
    author VARCHAR(100),
    body TEXT,
    score INTEGER DEFAULT 0,
    created_utc TIMESTAMP,
    depth INTEGER DEFAULT 0,
    is_submitter BOOLEAN DEFAULT FALSE,
    parent_id VARCHAR(20),
    edited BOOLEAN DEFAULT FALSE,
    extracted_entities JSONB DEFAULT '{}',
    idea_signals JSONB DEFAULT '{}',
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT reddit_comments_check_score CHECK (score >= 0),
    CONSTRAINT reddit_comments_check_depth CHECK (depth >= 0)
);

-- Reddit subreddits table
CREATE TABLE IF NOT EXISTS reddit_subreddits (
    name VARCHAR(100) PRIMARY KEY,
    title VARCHAR(255),
    description TEXT,
    subscribers INTEGER DEFAULT 0,
    active_users INTEGER DEFAULT 0,
    created_utc TIMESTAMP,
    public_description TEXT,
    subreddit_type VARCHAR(50),
    over18 BOOLEAN DEFAULT FALSE,
    advertiser_category VARCHAR(100),
    key_color VARCHAR(10),
    icon_img VARCHAR(500),
    banner_img VARCHAR(500),
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT reddit_subreddits_check_subscribers CHECK (subscribers >= 0),
    CONSTRAINT reddit_subreddits_check_active_users CHECK (active_users >= 0)
);

-- =============================================================================
-- PRODUCT HUNT DATA SCHEMA
-- =============================================================================

-- Product Hunt products table
CREATE TABLE IF NOT EXISTS producthunt_products (
    id VARCHAR(50) PRIMARY KEY,  -- Product Hunt product ID
    name VARCHAR(255) NOT NULL,
    tagline VARCHAR(500),
    description TEXT,
    url VARCHAR(1000),
    website VARCHAR(1000),
    redirect_url VARCHAR(1000),
    slug VARCHAR(255),
    created_at TIMESTAMP,
    featured_at TIMESTAMP,
    votes_count INTEGER DEFAULT 0,
    comments_count INTEGER DEFAULT 0,
    reviews_count INTEGER DEFAULT 0,
    maker_count INTEGER DEFAULT 0,
    thumbnail_url VARCHAR(1000),
    media_urls TEXT[] DEFAULT '{}',
    topics JSONB DEFAULT '[]',
    makers JSONB DEFAULT '[]',
    reviews JSONB DEFAULT '[]',
    extracted_entities JSONB DEFAULT '{}',
    market_signals JSONB DEFAULT '{}',
    idea_potential JSONB DEFAULT '{}',
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT producthunt_products_check_votes CHECK (votes_count >= 0),
    CONSTRAINT producthunt_products_check_comments CHECK (comments_count >= 0),
    CONSTRAINT producthunt_products_check_reviews CHECK (reviews_count >= 0),
    CONSTRAINT producthunt_products_check_makers CHECK (maker_count >= 0)
);

-- Product Hunt makers table
CREATE TABLE IF NOT EXISTS producthunt_makers (
    id VARCHAR(50) PRIMARY KEY,  -- Product Hunt maker ID
    name VARCHAR(255),
    username VARCHAR(100),
    headline TEXT,
    url VARCHAR(1000),
    twitter_username VARCHAR(100),
    profile_image VARCHAR(1000),
    follower_count INTEGER DEFAULT 0,
    made_products_count INTEGER DEFAULT 0,
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT producthunt_makers_check_followers CHECK (follower_count >= 0),
    CONSTRAINT producthunt_makers_check_products CHECK (made_products_count >= 0)
);

-- Product Hunt comments table
CREATE TABLE IF NOT EXISTS producthunt_comments (
    id VARCHAR(50) PRIMARY KEY,  -- Product Hunt comment ID
    product_id VARCHAR(50) REFERENCES producthunt_products(id) ON DELETE CASCADE,
    user_id VARCHAR(50),
    user_name VARCHAR(255),
    username VARCHAR(100),
    body TEXT,
    created_at TIMESTAMP,
    profile_image VARCHAR(1000),
    twitter_username VARCHAR(100),
    reply_count INTEGER DEFAULT 0,
    extracted_entities JSONB DEFAULT '{}',
    sentiment_signals JSONB DEFAULT '{}',
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT producthunt_comments_check_replies CHECK (reply_count >= 0)
);

-- Product Hunt topics table
CREATE TABLE IF NOT EXISTS producthunt_topics (
    id VARCHAR(50) PRIMARY KEY,  -- Product Hunt topic ID
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(255),
    description TEXT,
    followers_count INTEGER DEFAULT 0,
    posts_count INTEGER DEFAULT 0,
    image_url VARCHAR(1000),
    created_at TIMESTAMP,
    category VARCHAR(100),
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT producthunt_topics_check_followers CHECK (followers_count >= 0),
    CONSTRAINT producthunt_topics_check_posts CHECK (posts_count >= 0)
);

-- =============================================================================
-- GOOGLE TRENDS DATA SCHEMA
-- =============================================================================

-- Trending searches table
CREATE TABLE IF NOT EXISTS trending_searches (
    id VARCHAR(100) PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    traffic VARCHAR(50),
    summary TEXT,
    url VARCHAR(1000),
    source VARCHAR(255),
    image_url VARCHAR(1000),
    date DATE,
    geo VARCHAR(10),
    related_queries TEXT[] DEFAULT '{}',
    extracted_entities JSONB DEFAULT '{}',
    idea_signals JSONB DEFAULT '{}',
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE
);

-- Interest over time table
CREATE TABLE IF NOT EXISTS interest_over_time (
    id VARCHAR(100) PRIMARY KEY,
    keyword VARCHAR(255) NOT NULL,
    date DATE,
    interest_value INTEGER,
    formatted_value VARCHAR(20),
    geo VARCHAR(10),
    time_range VARCHAR(50),
    category INTEGER,
    search_type VARCHAR(20),
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT interest_over_time_check_value CHECK (interest_value >= 0 AND interest_value <= 100)
);

-- Related queries table
CREATE TABLE IF NOT EXISTS related_queries (
    id VARCHAR(100) PRIMARY KEY,
    main_keyword VARCHAR(255) NOT NULL,
    related_query VARCHAR(500),
    query_type VARCHAR(20), -- 'top' or 'rising'
    interest_value INTEGER,
    formatted_value VARCHAR(20),
    has_data BOOLEAN DEFAULT FALSE,
    geo VARCHAR(10),
    extracted_at TIMESTAMP,
    relationship_score DECIMAL(3,2),
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT related_queries_check_value CHECK (interest_value >= 0),
    CONSTRAINT related_queries_check_score CHECK (relationship_score >= 0 AND relationship_score <= 1)
);

-- Regional interest table
CREATE TABLE IF NOT EXISTS regional_interest (
    id VARCHAR(100) PRIMARY KEY,
    keyword VARCHAR(255) NOT NULL,
    geo VARCHAR(100),
    geo_code VARCHAR(10),
    interest_value INTEGER,
    formatted_value VARCHAR(20),
    has_data BOOLEAN DEFAULT FALSE,
    extracted_at TIMESTAMP,
    market_opportunity_score DECIMAL(3,2),
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT regional_interest_check_value CHECK (interest_value >= 0),
    CONSTRAINT regional_interest_check_score CHECK (market_opportunity_score >= 0 AND market_opportunity_score <= 1)
);

-- Trend analysis table
CREATE TABLE IF NOT EXISTS trend_analysis (
    id VARCHAR(100) PRIMARY KEY,
    keyword VARCHAR(255) NOT NULL,
    analysis_date DATE,
    average_interest DECIMAL(8,2),
    peak_interest INTEGER,
    peak_date DATE,
    growth_rate DECIMAL(8,2),
    volatility DECIMAL(8,2),
    market_maturity VARCHAR(50),
    seasonal_pattern BOOLEAN DEFAULT FALSE,
    geo_distribution JSONB DEFAULT '{}',
    related_keywords TEXT[] DEFAULT '{}',
    idea_potential_score DECIMAL(5,2),
    recommendations JSONB DEFAULT '[]',
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT trend_analysis_check_avg_interest CHECK (average_interest >= 0),
    CONSTRAINT trend_analysis_check_peak_interest CHECK (peak_interest >= 0 AND peak_interest <= 100),
    CONSTRAINT trend_analysis_check_growth_rate CHECK (growth_rate >= -100 AND growth_rate <= 100),
    CONSTRAINT trend_analysis_check_volatility CHECK (volatility >= 0),
    CONSTRAINT trend_analysis_check_idea_score CHECK (idea_potential_score >= 0 AND idea_potential_score <= 100)
);

-- =============================================================================
-- TWITTER/X DATA SCHEMA
-- =============================================================================

-- Twitter tweets table
CREATE TABLE IF NOT EXISTS twitter_tweets (
    id VARCHAR(50) PRIMARY KEY,  -- Twitter tweet ID
    text TEXT NOT NULL,
    author_id VARCHAR(50),
    author_username VARCHAR(100),
    author_name VARCHAR(255),
    created_at TIMESTAMP,
    lang VARCHAR(10),
    source VARCHAR(255),
    reply_settings VARCHAR(50),
    possibly_sensitive BOOLEAN DEFAULT FALSE,
    public_metrics JSONB DEFAULT '{}',
    entities JSONB DEFAULT '{}',
    context_annotations JSONB DEFAULT '[]',
    attachments JSONB DEFAULT '{}',
    geo JSONB DEFAULT '{}',
    referenced_tweets JSONB DEFAULT '[]',
    in_reply_to_user_id VARCHAR(50),
    conversation_id VARCHAR(50),
    extracted_entities JSONB DEFAULT '{}',
    sentiment_analysis JSONB DEFAULT '{}',
    idea_signals JSONB DEFAULT '{}',
    market_insights JSONB DEFAULT '{}',
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE
);

-- Twitter users table
CREATE TABLE IF NOT EXISTS twitter_users (
    id VARCHAR(50) PRIMARY KEY,  -- Twitter user ID
    username VARCHAR(100) NOT NULL,
    name VARCHAR(255),
    description TEXT,
    location VARCHAR(255),
    url VARCHAR(1000),
    profile_image_url VARCHAR(1000),
    protected BOOLEAN DEFAULT FALSE,
    verified BOOLEAN DEFAULT FALSE,
    verified_type VARCHAR(50),
    created_at TIMESTAMP,
    pinned_tweet_id VARCHAR(50),
    public_metrics JSONB DEFAULT '{}',
    influence_score DECIMAL(5,3),
    specialization JSONB DEFAULT '{}',
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT twitter_users_check_influence CHECK (influence_score >= 0 AND influence_score <= 1)
);

-- Twitter trending topics table
CREATE TABLE IF NOT EXISTS twitter_trending_topics (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    query VARCHAR(500),
    url VARCHAR(1000),
    promoted_content BOOLEAN DEFAULT FALSE,
    tweet_volume INTEGER,
    woeid INTEGER,
    location_name VARCHAR(255),
    created_at TIMESTAMP,
    category VARCHAR(100),
    extracted_entities JSONB DEFAULT '{}',
    business_opportunity JSONB DEFAULT '{}',
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT twitter_trending_check_volume CHECK (tweet_volume >= 0)
);

-- Twitter hashtags table
CREATE TABLE IF NOT EXISTS twitter_hashtags (
    id VARCHAR(100) PRIMARY KEY,
    hashtag VARCHAR(255) NOT NULL,
    tweet_id VARCHAR(50) REFERENCES twitter_tweets(id) ON DELETE CASCADE,
    user_id VARCHAR(50),
    created_at TIMESTAMP,
    context INTEGER, -- position in tweet
    sentiment VARCHAR(20),
    reach INTEGER,
    engagement_rate DECIMAL(5,2),
    trend_score DECIMAL(3,3),
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT twitter_hashtags_check_reach CHECK (reach >= 0),
    CONSTRAINT twitter_hashtags_check_engagement CHECK (engagement_rate >= 0),
    CONSTRAINT twitter_hashtags_check_trend_score CHECK (trend_score >= 0 AND trend_score <= 1)
);

-- Twitter conversations table
CREATE TABLE IF NOT EXISTS twitter_conversations (
    id VARCHAR(100) PRIMARY KEY,
    conversation_id VARCHAR(50) NOT NULL,
    tweet_id VARCHAR(50) REFERENCES twitter_tweets(id) ON DELETE CASCADE,
    author_id VARCHAR(50),
    text TEXT,
    created_at TIMESTAMP,
    reply_to_tweet_id VARCHAR(50),
    reply_to_user_id VARCHAR(50),
    conversation_depth INTEGER DEFAULT 1,
    sentiment VARCHAR(20),
    topic_sentiment JSONB DEFAULT '{}',
    key_insights JSONB DEFAULT '[]',
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_id VARCHAR(100),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT twitter_conversations_check_depth CHECK (conversation_depth >= 1)
);

-- =============================================================================
-- CROSS-PLATFORM ANALYSIS TABLES
-- =============================================================================

-- Consolidated trending topics across platforms
CREATE TABLE IF NOT EXISTS consolidated_trends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    topic VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL, -- 'reddit', 'producthunt', 'trends', 'twitter'
    platform_id VARCHAR(100), -- Original ID from platform
    title VARCHAR(500),
    description TEXT,
    url VARCHAR(1000),
    engagement_score DECIMAL(8,2),
    sentiment_score DECIMAL(3,2),
    idea_potential_score DECIMAL(5,2),
    keywords TEXT[] DEFAULT '{}',
    entities JSONB DEFAULT '{}',
    created_at TIMESTAMP,
    discovered_at TIMESTAMP DEFAULT NOW(),
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT consolidated_trends_check_engagement CHECK (engagement_score >= 0),
    CONSTRAINT consolidated_trends_check_sentiment CHECK (sentiment_score >= -1 AND sentiment_score <= 1),
    CONSTRAINT consolidated_trends_check_idea_score CHECK (idea_potential_score >= 0 AND idea_potential_score <= 100)
);

-- Idea signals and opportunities
CREATE TABLE IF NOT EXISTS idea_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_platform VARCHAR(50) NOT NULL,
    source_id VARCHAR(100),
    signal_type VARCHAR(100), -- 'problem_statement', 'idea_request', 'success_story', 'pain_point'
    title VARCHAR(500),
    description TEXT,
    confidence_score DECIMAL(3,2),
    market_size_indicator VARCHAR(50),
    urgency_level VARCHAR(20),
    target_audience VARCHAR(100),
    keywords TEXT[] DEFAULT '{}',
    entities JSONB DEFAULT '{}',
    extraction_date TIMESTAMP DEFAULT NOW(),
    valid_until TIMESTAMP,
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT idea_signals_check_confidence CHECK (confidence_score >= 0 AND confidence_score <= 1)
);

-- Market opportunity tracking
CREATE TABLE IF NOT EXISTS market_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    opportunity_name VARCHAR(255) NOT NULL,
    description TEXT,
    trend_sources TEXT[] DEFAULT '{}', -- Platform names where this trend was detected
    combined_engagement_score DECIMAL(10,2),
    market_validation_level VARCHAR(50), -- 'high', 'medium', 'low'
    competition_level VARCHAR(50), -- 'high', 'medium', 'low'
    entry_difficulty VARCHAR(50), -- 'easy', 'medium', 'hard'
    estimated_market_size VARCHAR(100),
    target_audience_size VARCHAR(100),
    recommended_actions JSONB DEFAULT '[]',
    potential_score DECIMAL(5,2),
    created_at TIMESTAMP DEFAULT NOW(),
    last_updated TIMESTAMP DEFAULT NOW(),
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'archived', 'rejected'
    raw_data JSONB DEFAULT '{}',

    -- Metadata
    fivetran_synced TIMESTAMP DEFAULT NOW(),
    fivetran_deleted BOOLEAN DEFAULT FALSE,

    -- Constraints
    CONSTRAINT market_opportunities_check_score CHECK (potential_score >= 0 AND potential_score <= 100)
);

-- =============================================================================
-- INDEXES FOR PERFORMANCE
-- =============================================================================

-- Reddit indexes
CREATE INDEX IF NOT EXISTS idx_reddit_posts_created_at ON reddit_posts(created_utc DESC);
CREATE INDEX IF NOT EXISTS idx_reddit_posts_subreddit ON reddit_posts(subreddit);
CREATE INDEX IF NOT EXISTS idx_reddit_posts_score ON reddit_posts(score DESC);
CREATE INDEX IF NOT EXISTS idx_reddit_comments_post_id ON reddit_comments(post_id);
CREATE INDEX IF NOT EXISTS idx_reddit_comments_created_at ON reddit_comments(created_utc DESC);

-- Product Hunt indexes
CREATE INDEX IF NOT EXISTS idx_producthunt_products_created_at ON producthunt_products(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_producthunt_products_votes ON producthunt_products(votes_count DESC);
CREATE INDEX IF NOT EXISTS idx_producthunt_products_featured ON producthunt_products(featured_at DESC);
CREATE INDEX IF NOT EXISTS idx_producthunt_comments_product_id ON producthunt_comments(product_id);

-- Google Trends indexes
CREATE INDEX IF NOT EXISTS idx_trending_searches_date_geo ON trending_searches(date DESC, geo);
CREATE INDEX IF NOT EXISTS idx_interest_over_time_keyword_date ON interest_over_time(keyword, date DESC);
CREATE INDEX IF NOT EXISTS idx_related_queries_keyword ON related_queries(main_keyword);
CREATE INDEX IF NOT EXISTS idx_regional_interest_keyword_geo ON regional_interest(keyword, geo);
CREATE INDEX IF NOT EXISTS idx_trend_analysis_keyword_date ON trend_analysis(keyword, analysis_date DESC);

-- Twitter indexes
CREATE INDEX IF NOT EXISTS idx_twitter_tweets_created_at ON twitter_tweets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_twitter_tweets_author_id ON twitter_tweets(author_id);
CREATE INDEX IF NOT EXISTS idx_twitter_tweets_conversation_id ON twitter_tweets(conversation_id);
CREATE INDEX IF NOT EXISTS idx_twitter_users_username ON twitter_users(username);
CREATE INDEX IF NOT EXISTS idx_twitter_hashtags_hashtag ON twitter_hashtags(hashtag);
CREATE INDEX IF NOT EXISTS idx_twitter_conversations_conversation_id ON twitter_conversations(conversation_id);

-- Cross-platform indexes
CREATE INDEX IF NOT EXISTS idx_consolidated_trends_platform ON consolidated_trends(platform, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_consolidated_trends_engagement ON consolidated_trends(engagement_score DESC);
CREATE INDEX IF NOT EXISTS idx_idea_signals_type_date ON idea_signals(signal_type, extraction_date DESC);
CREATE INDEX IF NOT EXISTS idx_market_opportunities_score ON market_opportunities(potential_score DESC);
CREATE INDEX IF NOT EXISTS idx_market_opportunities_status ON market_opportunities(status, last_updated DESC);

-- =============================================================================
-- TRIGGERS FOR UPDATED_AT
-- =============================================================================

-- Create updated_at function if it doesn't exist
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.fivetran_synced = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply triggers to tables that need updated_at functionality
CREATE TRIGGER update_reddit_posts_synced BEFORE UPDATE ON reddit_posts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_reddit_comments_synced BEFORE UPDATE ON reddit_comments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_reddit_subreddits_synced BEFORE UPDATE ON reddit_subreddits
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_producthunt_products_synced BEFORE UPDATE ON producthunt_products
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_producthunt_makers_synced BEFORE UPDATE ON producthunt_makers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_producthunt_comments_synced BEFORE UPDATE ON producthunt_comments
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_producthunt_topics_synced BEFORE UPDATE ON producthunt_topics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_trending_searches_synced BEFORE UPDATE ON trending_searches
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_twitter_tweets_synced BEFORE UPDATE ON twitter_tweets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_twitter_users_synced BEFORE UPDATE ON twitter_users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_twitter_trending_topics_synced BEFORE UPDATE ON twitter_trending_topics
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_market_opportunities_updated BEFORE UPDATE ON market_opportunities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- =============================================================================
-- VIEWS FOR ANALYSIS
-- =============================================================================

-- High-potential ideas across platforms
CREATE OR REPLACE VIEW high_potential_ideas AS
SELECT
    id,
    title,
    description,
    platform,
    engagement_score,
    idea_potential_score,
    created_at,
    CASE
        WHEN idea_potential_score >= 80 THEN 'Very High'
        WHEN idea_potential_score >= 60 THEN 'High'
        WHEN idea_potential_score >= 40 THEN 'Medium'
        ELSE 'Low'
    END as priority_level
FROM consolidated_trends
WHERE idea_potential_score >= 40
ORDER BY idea_potential_score DESC, created_at DESC;

-- Trending keywords across platforms
CREATE OR REPLACE VIEW trending_keywords AS
SELECT
    keyword,
    COUNT(*) as platform_count,
    AVG(engagement_score) as avg_engagement,
    MAX(engagement_score) as max_engagement,
    array_agg(DISTINCT platform) as platforms
FROM consolidated_trends
WHERE created_at >= NOW() - INTERVAL '7 days'
GROUP BY keyword
HAVING COUNT(*) > 1
ORDER BY avg_engagement DESC, platform_count DESC;

-- Problem statements and pain points
CREATE OR REPLACE VIEW market_problems AS
SELECT
    id,
    title,
    description,
    source_platform,
    confidence_score,
    target_audience,
    keywords,
    extraction_date
FROM idea_signals
WHERE signal_type IN ('problem_statement', 'pain_point')
  AND valid_until > NOW()
ORDER BY confidence_score DESC, extraction_date DESC;

-- Market opportunity summary
CREATE OR REPLACE VIEW opportunity_summary AS
SELECT
    opportunity_name,
    description,
    combined_engagement_score,
    market_validation_level,
    competition_level,
    entry_difficulty,
    potential_score,
    array_to_string(trend_sources, ', ') as sources
FROM market_opportunities
WHERE status = 'active'
ORDER BY potential_score DESC;

-- =============================================================================
-- SAMPLE DATA (Optional - for testing)
-- =============================================================================

-- Insert sample trend data for testing
INSERT INTO consolidated_trends (topic, platform, platform_id, title, description, engagement_score, idea_potential_score, keywords, created_at) VALUES
('AI Automation Tools', 'reddit', 'abc123', 'Looking for AI automation tools for small business', 'User seeking AI tools to automate business processes', 850.5, 75.0, ARRAY['ai', 'automation', 'business', 'tools'], NOW() - INTERVAL '2 days'),
('No-Code Platforms', 'producthunt', 'def456', 'BuildInPublic - No-Code Platform', 'Build and launch apps without coding', 2500.0, 85.0, ARRAY['nocode', 'platform', 'apps', 'build'], NOW() - INTERVAL '1 day'),
('Remote Work Productivity', 'twitter', 'ghi789', '#RemoteWork productivity hacks thread', 'Tips and tools for remote work productivity', 1200.0, 65.0, ARRAY['remote', 'work', 'productivity', 'tools'], NOW() - INTERVAL '3 hours')
ON CONFLICT DO NOTHING;

-- Insert sample market opportunity
INSERT INTO market_opportunities (opportunity_name, description, trend_sources, combined_engagement_score, market_validation_level, potential_score) VALUES
('AI-Powered Customer Support', 'AI chatbots and automation tools for customer service', ARRAY['reddit', 'twitter', 'producthunt'], 4550.5, 'high', 78.5),
('No-Code Business Automation', 'Visual platforms for automating business workflows', ARRAY['producthunt', 'trends'], 3200.0, 'medium', 82.0),
('Remote Team Collaboration Tools', 'Enhanced collaboration tools for distributed teams', ARRAY['twitter', 'reddit'], 2800.0, 'high', 71.5)
ON CONFLICT DO NOTHING;