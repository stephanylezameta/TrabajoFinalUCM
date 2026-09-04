SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    title TEXT,
    destination TEXT,
    hotel TEXT,
    price REAL,
    currency TEXT DEFAULT 'EUR',
    duration_days INTEGER,
    nights INTEGER,
    departure_date TEXT,
    return_date TEXT,
    rating REAL,
    board_basis TEXT,
    transport TEXT,
    airline TEXT,
    availability REAL,
    discount REAL,
    description TEXT,
    image_url TEXT,
    detail_url TEXT,
    source TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    extra_data TEXT
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT,
    started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at TEXT,
    source TEXT,
    medium TEXT,
    campaign TEXT,
    device TEXT,
    country TEXT
);

CREATE TABLE IF NOT EXISTS events (
    event_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,
    user_id TEXT,
    page TEXT,
    event_type TEXT NOT NULL,
    element_id TEXT,
    product_id TEXT,
    destination TEXT,
    source TEXT,
    medium TEXT,
    campaign TEXT,
    device TEXT,
    country TEXT,
    response_time_ms REAL,
    metadata TEXT,
    dedupe_key TEXT UNIQUE,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id),
    FOREIGN KEY(product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS bookings (
    booking_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    session_id TEXT,
    user_id TEXT,
    product_id TEXT,
    passengers INTEGER,
    room_nights INTEGER,
    revenue_eur REAL,
    cost_eur REAL,
    margin_eur REAL,
    status TEXT NOT NULL DEFAULT 'started',
    cancelled_at TEXT,
    FOREIGN KEY(session_id) REFERENCES sessions(session_id),
    FOREIGN KEY(product_id) REFERENCES products(product_id)
);

CREATE TABLE IF NOT EXISTS destinations (
    destination_id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    zone TEXT,
    country_label TEXT,
    country_name TEXT,
    affinity REAL,
    demand REAL,
    occupancy REAL,
    local_impact REAL,
    seasonality REAL,
    accessibility REAL,
    sustainability REAL,
    reference_price_eur REAL,
    co2_kg REAL,
    source TEXT,
    extra_data TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS climate_observations (
    destination_name TEXT NOT NULL,
    year_month TEXT NOT NULL,
    air_temp_c REAL,
    water_temp_c REAL,
    precipitation_mm REAL,
    rain_days REAL,
    sun_hours REAL,
    humidity_pct REAL,
    source TEXT,
    PRIMARY KEY(destination_name, year_month)
);

CREATE TABLE IF NOT EXISTS connectivity_stats (
    destination_name TEXT PRIMARY KEY,
    destination_group TEXT,
    iata_destination TEXT,
    direct_routes_es REAL,
    direct_routes_uk REAL,
    direct_routes_de REAL,
    weekly_flights REAL,
    weekly_seats REAL,
    weekly_passengers REAL,
    annual_passengers REAL,
    source TEXT
);

CREATE TABLE IF NOT EXISTS country_indicators (
    iso TEXT PRIMARY KEY,
    country_name TEXT,
    hospital_beds_per_1000 REAL,
    homicide_rate_per_100k REAL,
    source TEXT
);

CREATE TABLE IF NOT EXISTS imports (
    import_id TEXT PRIMARY KEY,
    imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    source_name TEXT,
    source_type TEXT,
    row_count INTEGER,
    status TEXT,
    details TEXT
);

CREATE INDEX IF NOT EXISTS idx_products_destination ON products(destination);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_bookings_session ON bookings(session_id);
CREATE INDEX IF NOT EXISTS idx_climate_destination ON climate_observations(destination_name);
"""
