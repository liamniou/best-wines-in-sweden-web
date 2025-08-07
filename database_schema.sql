-- Wine Database Schema for Best Wines Sweden
-- Migrating from Telegraph pages to database-driven website

-- Table for storing Vivino toplists
CREATE TABLE toplists (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    url VARCHAR(500) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(100), -- price range, style, region, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table for storing wine data from Vivino
CREATE TABLE vivino_wines (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    rating DECIMAL(3,2) NOT NULL,
    vintage_id VARCHAR(50),
    wine_url VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Table for storing Systembolaget products
CREATE TABLE systembolaget_products (
    id SERIAL PRIMARY KEY,
    product_number VARCHAR(50) UNIQUE NOT NULL,
    name_bold VARCHAR(255),
    name_thin VARCHAR(255),
    full_name VARCHAR(500) GENERATED ALWAYS AS (CONCAT(name_bold, ' ', name_thin)) STORED,
    price DECIMAL(8,2),
    volume INTEGER, -- in ml
    category_level1 VARCHAR(100), -- Vin, Öl, etc.
    category_level2 VARCHAR(100), -- Rött vin, Vitt vin, etc.
    country VARCHAR(100),
    alcohol_percentage DECIMAL(4,2),
    producer VARCHAR(255),
    year INTEGER,
    stock_status VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Junction table linking Vivino wines to toplists
CREATE TABLE toplist_wines (
    id SERIAL PRIMARY KEY,
    toplist_id INTEGER REFERENCES toplists(id) ON DELETE CASCADE,
    vivino_wine_id INTEGER REFERENCES vivino_wines(id) ON DELETE CASCADE,
    position INTEGER, -- position in the toplist
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(toplist_id, vivino_wine_id)
);

-- Table for wine matching results between Vivino and Systembolaget
CREATE TABLE wine_matches (
    id SERIAL PRIMARY KEY,
    vivino_wine_id INTEGER REFERENCES vivino_wines(id) ON DELETE CASCADE,
    systembolaget_product_id INTEGER REFERENCES systembolaget_products(id) ON DELETE CASCADE,
    match_score DECIMAL(5,2), -- similarity score percentage
    match_type VARCHAR(50), -- exact, partial, fuzzy, different, uncertain
    verified BOOLEAN DEFAULT FALSE, -- manual verification flag
    ai_reasoning TEXT, -- AI explanation for the match decision
    match_method VARCHAR(20) DEFAULT 'ai', -- ai, fallback
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(vivino_wine_id, systembolaget_product_id)
);

-- Table for user favorites and ratings
CREATE TABLE user_favorites (
    id SERIAL PRIMARY KEY,
    user_session VARCHAR(255), -- for anonymous users
    wine_match_id INTEGER REFERENCES wine_matches(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_session, wine_match_id)
);

-- Table for tracking data updates
CREATE TABLE update_log (
    id SERIAL PRIMARY KEY,
    toplist_id INTEGER REFERENCES toplists(id),
    status VARCHAR(50), -- success, failed, in_progress
    wines_found INTEGER,
    matches_found INTEGER,
    error_message TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_vivino_wines_rating ON vivino_wines(rating DESC);
CREATE INDEX idx_systembolaget_price ON systembolaget_products(price);
CREATE INDEX idx_systembolaget_country ON systembolaget_products(country);
CREATE INDEX idx_systembolaget_category ON systembolaget_products(category_level2);
CREATE INDEX idx_wine_matches_score ON wine_matches(match_score DESC);
CREATE INDEX idx_toplist_wines_position ON toplist_wines(toplist_id, position);

-- Full text search indexes
CREATE INDEX idx_systembolaget_fulltext ON systembolaget_products 
USING gin(to_tsvector('simple', full_name));
CREATE INDEX idx_vivino_fulltext ON vivino_wines 
USING gin(to_tsvector('simple', name));

-- Views for common queries
CREATE VIEW wine_matches_with_details AS
SELECT 
    wm.id as match_id,
    wm.match_score,
    wm.match_type,
    wm.verified,
    wm.ai_reasoning,
    wm.match_method,
    vw.name as vivino_name,
    vw.rating as vivino_rating,
    CONCAT(sp.name_bold, ' ', sp.name_thin) as systembolaget_name,
    sp.price,
    sp.category_level2 as wine_style,
    sp.country,
    sp.product_number,
    sp.alcohol_percentage,
    sp.year,
    sp.producer,
    wm.created_at as match_created_at
FROM wine_matches wm
JOIN vivino_wines vw ON wm.vivino_wine_id = vw.id
JOIN systembolaget_products sp ON wm.systembolaget_product_id = sp.id;

CREATE VIEW toplist_summary AS
SELECT 
    t.id,
    t.name,
    t.category,
    COUNT(tw.vivino_wine_id) as wine_count,
    COUNT(wm.id) as match_count,
    AVG(vw.rating) as avg_rating,
    t.updated_at
FROM toplists t
LEFT JOIN toplist_wines tw ON t.id = tw.toplist_id
LEFT JOIN vivino_wines vw ON tw.vivino_wine_id = vw.id
LEFT JOIN wine_matches wm ON vw.id = wm.vivino_wine_id
GROUP BY t.id, t.name, t.category, t.updated_at;