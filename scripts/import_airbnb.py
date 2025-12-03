#!/usr/bin/env python3
"""
PG Index Agents - Script de importacion Airbnb
https://github.com/686f6c61/pg-index-agents

Script para descargar e importar datos de Inside Airbnb en PostgreSQL.
Ideal para probar el agente Partitioner con tablas grandes.

Fuente de datos: insideairbnb.com
Los datos son publicos y se actualizan mensualmente.

Tablas creadas:
    - neighbourhoods: Barrios de la ciudad (~300 rows)
    - hosts: Anfitriones extraidos de listings
    - listings: Propiedades en alquiler (~50K rows)
    - reviews: Resenas de huespedes (~500K rows)
    - calendar: Disponibilidad y precios (~18M rows)

La tabla calendar es muy grande y puede tardar en importarse.
Usar --skip-calendar para una importacion mas rapida.

Vistas materializadas:
    - neighbourhood_stats: Estadisticas por barrio
    - host_stats: Estadisticas por anfitrion

Ciudades disponibles:
    - amsterdam (default)

Uso:
    python import_airbnb.py --city amsterdam --skip-calendar

Requisitos:
    - PostgreSQL 14+
    - Python packages: psycopg2, requests, tqdm

Autor: 686f6c61
Licencia: MIT
"""

import os
import sys
import argparse
import gzip
import csv
import io
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
import requests
from tqdm import tqdm

# Configuration - Override via environment variables
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': int(os.getenv('DB_PORT', 5432)),
    'database': os.getenv('DB_NAME', 'airbnb_sample'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
}

# Inside Airbnb data URLs
# Format: http://data.insideairbnb.com/{country}/{region}/{city}/{date}/data/{file}
CITIES = {
    'amsterdam': {
        'city': 'amsterdam',
        'base_url': 'http://data.insideairbnb.com/the-netherlands/north-holland/amsterdam',
        'date': '2024-09-05',
    },
}

FILES = {
    'listings': 'listings.csv.gz',
    'listings_detailed': 'listings.csv.gz',  # Same file, detailed version
    'reviews': 'reviews.csv.gz',
    'calendar': 'calendar.csv.gz',
    'neighbourhoods': 'neighbourhoods.csv',
}

# SQL Schema
SCHEMA_SQL = """
-- Airbnb Sample Database Schema
-- Based on Inside Airbnb data structure

DROP TABLE IF EXISTS reviews CASCADE;
DROP TABLE IF EXISTS calendar CASCADE;
DROP TABLE IF EXISTS listings CASCADE;
DROP TABLE IF EXISTS neighbourhoods CASCADE;
DROP TABLE IF EXISTS hosts CASCADE;

-- Neighbourhoods table
CREATE TABLE neighbourhoods (
    id SERIAL PRIMARY KEY,
    city VARCHAR(50) DEFAULT 'amsterdam',
    neighbourhood_group VARCHAR(255),
    neighbourhood VARCHAR(255) NOT NULL,
    UNIQUE(neighbourhood)
);

-- Hosts table (extracted from listings)
CREATE TABLE hosts (
    id BIGINT PRIMARY KEY,
    name VARCHAR(255),
    url TEXT,
    since DATE,
    location VARCHAR(512),
    about TEXT,
    response_time VARCHAR(100),
    response_rate VARCHAR(20),
    acceptance_rate VARCHAR(20),
    is_superhost BOOLEAN DEFAULT FALSE,
    thumbnail_url TEXT,
    picture_url TEXT,
    neighbourhood VARCHAR(255),
    listings_count INTEGER DEFAULT 0,
    total_listings_count INTEGER DEFAULT 0,
    verifications TEXT,
    has_profile_pic BOOLEAN DEFAULT TRUE,
    identity_verified BOOLEAN DEFAULT FALSE
);

-- Listings table
CREATE TABLE listings (
    id BIGINT PRIMARY KEY,
    city VARCHAR(50) DEFAULT 'amsterdam',
    listing_url TEXT,
    scrape_id BIGINT,
    last_scraped DATE,
    source VARCHAR(100),
    name TEXT,
    description TEXT,
    neighborhood_overview TEXT,
    picture_url TEXT,
    host_id BIGINT REFERENCES hosts(id) ON DELETE SET NULL,
    neighbourhood VARCHAR(255),
    neighbourhood_cleansed VARCHAR(255),
    neighbourhood_group_cleansed VARCHAR(255),
    latitude DECIMAL(10, 7),
    longitude DECIMAL(10, 7),
    property_type VARCHAR(100),
    room_type VARCHAR(50),
    accommodates INTEGER,
    bathrooms DECIMAL(5, 2),
    bathrooms_text VARCHAR(100),
    bedrooms INTEGER,
    beds INTEGER,
    amenities TEXT,
    price DECIMAL(10, 2),
    minimum_nights INTEGER,
    maximum_nights INTEGER,
    minimum_minimum_nights INTEGER,
    maximum_minimum_nights INTEGER,
    minimum_maximum_nights INTEGER,
    maximum_maximum_nights INTEGER,
    minimum_nights_avg_ntm DOUBLE PRECISION,
    maximum_nights_avg_ntm DOUBLE PRECISION,
    calendar_updated DATE,
    has_availability BOOLEAN,
    availability_30 INTEGER,
    availability_60 INTEGER,
    availability_90 INTEGER,
    availability_365 INTEGER,
    calendar_last_scraped DATE,
    number_of_reviews INTEGER DEFAULT 0,
    number_of_reviews_ltm INTEGER DEFAULT 0,
    number_of_reviews_l30d INTEGER DEFAULT 0,
    first_review DATE,
    last_review DATE,
    review_scores_rating DECIMAL(5, 2),
    review_scores_accuracy DECIMAL(5, 2),
    review_scores_cleanliness DECIMAL(5, 2),
    review_scores_checkin DECIMAL(5, 2),
    review_scores_communication DECIMAL(5, 2),
    review_scores_location DECIMAL(5, 2),
    review_scores_value DECIMAL(5, 2),
    license TEXT,
    instant_bookable BOOLEAN DEFAULT FALSE,
    calculated_host_listings_count INTEGER,
    calculated_host_listings_count_entire_homes INTEGER,
    calculated_host_listings_count_private_rooms INTEGER,
    calculated_host_listings_count_shared_rooms INTEGER,
    reviews_per_month DECIMAL(6, 2)
);

-- Reviews table
CREATE TABLE reviews (
    id BIGINT PRIMARY KEY,
    listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    reviewer_id BIGINT,
    reviewer_name VARCHAR(255),
    comments TEXT
);

-- Calendar table (availability and pricing)
CREATE TABLE calendar (
    id SERIAL,
    listing_id BIGINT NOT NULL REFERENCES listings(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    available BOOLEAN,
    price DECIMAL(10, 2),
    adjusted_price DECIMAL(10, 2),
    minimum_nights INTEGER,
    maximum_nights INTEGER,
    PRIMARY KEY (listing_id, date)
);

-- Indexes for common query patterns
CREATE INDEX idx_listings_host ON listings(host_id);
CREATE INDEX idx_listings_neighbourhood ON listings(neighbourhood_cleansed);
CREATE INDEX idx_listings_room_type ON listings(room_type);
CREATE INDEX idx_listings_price ON listings(price);
CREATE INDEX idx_listings_location ON listings(latitude, longitude);
CREATE INDEX idx_listings_rating ON listings(review_scores_rating);
CREATE INDEX idx_listings_availability ON listings(availability_30, availability_60, availability_90);

CREATE INDEX idx_reviews_listing ON reviews(listing_id);
CREATE INDEX idx_reviews_date ON reviews(date);
CREATE INDEX idx_reviews_reviewer ON reviews(reviewer_id);

CREATE INDEX idx_calendar_date ON calendar(date);
CREATE INDEX idx_calendar_available ON calendar(available);
CREATE INDEX idx_calendar_price ON calendar(price);

CREATE INDEX idx_hosts_superhost ON hosts(is_superhost);
CREATE INDEX idx_hosts_listings ON hosts(listings_count);

-- Create materialized view for neighbourhood statistics
CREATE MATERIALIZED VIEW neighbourhood_stats AS
SELECT
    neighbourhood_cleansed as neighbourhood,
    COUNT(*) as listing_count,
    AVG(price) as avg_price,
    AVG(review_scores_rating) as avg_rating,
    SUM(number_of_reviews) as total_reviews
FROM listings
GROUP BY neighbourhood_cleansed;

CREATE UNIQUE INDEX idx_neighbourhood_stats ON neighbourhood_stats(neighbourhood);

-- Create materialized view for host statistics
CREATE MATERIALIZED VIEW host_stats AS
SELECT
    host_id,
    COUNT(*) as listings,
    AVG(price) as avg_price,
    SUM(number_of_reviews) as total_reviews,
    AVG(review_scores_rating) as avg_rating
FROM listings
WHERE host_id IS NOT NULL
GROUP BY host_id;

CREATE INDEX idx_host_stats ON host_stats(host_id);

-- Full-text search indexes
CREATE INDEX idx_listings_name_fts ON listings USING gin(to_tsvector('english', COALESCE(name, '')));
CREATE INDEX idx_listings_desc_fts ON listings USING gin(to_tsvector('english', COALESCE(description, '')));
CREATE INDEX idx_reviews_comments_fts ON reviews USING gin(to_tsvector('english', COALESCE(comments, '')));
"""


def download_file(url: str, desc: str = "Downloading") -> bytes:
    """Download a file and return content."""
    try:
        print(f"Downloading: {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))

        content = io.BytesIO()
        with tqdm(total=total_size, unit='B', unit_scale=True, desc=desc) as pbar:
            for chunk in response.iter_content(chunk_size=8192):
                content.write(chunk)
                pbar.update(len(chunk))

        return content.getvalue()
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return None


def safe_float(value, default=None):
    """Safely convert to float."""
    if value is None or value == '' or value == 'N/A':
        return default
    try:
        # Remove $ and , from price strings
        clean_value = str(value).replace('$', '').replace(',', '').strip()
        return float(clean_value)
    except (ValueError, TypeError):
        return default


def safe_int(value, default=None):
    """Safely convert to int."""
    if value is None or value == '' or value == 'N/A':
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_bool(value, default=False):
    """Safely convert to bool."""
    if value is None or value == '':
        return default
    return str(value).lower() in ('t', 'true', '1', 'yes')


def safe_date(value, default=None):
    """Safely convert to date."""
    if value is None or value == '':
        return default
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return default


def safe_str(value, max_length=None, default=None):
    """Safely convert to string with optional max length."""
    if value is None or value == '':
        return default
    result = str(value)
    if max_length and len(result) > max_length:
        result = result[:max_length]
    return result


def create_database():
    """Create the database if it doesn't exist."""
    conn = psycopg2.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        database='postgres',
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
    )
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (DB_CONFIG['database'],))
    if not cur.fetchone():
        cur.execute(f"CREATE DATABASE {DB_CONFIG['database']}")
        print(f"Created database: {DB_CONFIG['database']}")
    else:
        print(f"Database {DB_CONFIG['database']} already exists")

    cur.close()
    conn.close()


def get_connection():
    """Get database connection."""
    return psycopg2.connect(**DB_CONFIG)


def parse_csv_gz(content: bytes):
    """Parse gzipped CSV content."""
    try:
        decompressed = gzip.decompress(content)
        text = decompressed.decode('utf-8')
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)
    except Exception as e:
        print(f"Error parsing CSV: {e}")
        return []


def parse_csv(content: bytes):
    """Parse CSV content."""
    try:
        text = content.decode('utf-8')
        reader = csv.DictReader(io.StringIO(text))
        return list(reader)
    except Exception as e:
        print(f"Error parsing CSV: {e}")
        return []


def import_neighbourhoods(city_config: dict, conn):
    """Import neighbourhoods data."""
    url = f"{city_config['base_url']}/{city_config['date']}/visualisations/neighbourhoods.csv"
    content = download_file(url, "Neighbourhoods")
    if not content:
        print("Failed to download neighbourhoods data")
        return

    rows = parse_csv(content)
    if not rows:
        return

    cur = conn.cursor()
    batch = []

    for row in rows:
        batch.append((
            row.get('neighbourhood_group'),
            row.get('neighbourhood'),
        ))

    if batch:
        execute_values(cur, """
            INSERT INTO neighbourhoods (neighbourhood_group, neighbourhood)
            VALUES %s ON CONFLICT (neighbourhood) DO NOTHING
        """, batch)
        conn.commit()

    cur.close()
    print(f"Imported {len(batch)} neighbourhoods")


def import_listings(city_config: dict, conn):
    """Import listings data (detailed version)."""
    url = f"{city_config['base_url']}/{city_config['date']}/data/listings.csv.gz"
    content = download_file(url, "Listings")
    if not content:
        print("Failed to download listings data")
        return

    rows = parse_csv_gz(content)
    if not rows:
        return

    cur = conn.cursor()

    # First, extract and import unique hosts
    print("Extracting hosts...")
    hosts = {}
    for row in rows:
        host_id = safe_int(row.get('host_id'))
        if host_id and host_id not in hosts:
            hosts[host_id] = (
                host_id,
                safe_str(row.get('host_name'), 255),
                row.get('host_url'),
                safe_date(row.get('host_since')),
                safe_str(row.get('host_location'), 512),
                row.get('host_about'),
                safe_str(row.get('host_response_time'), 100),
                safe_str(row.get('host_response_rate'), 20),
                safe_str(row.get('host_acceptance_rate'), 20),
                safe_bool(row.get('host_is_superhost')),
                row.get('host_thumbnail_url'),
                row.get('host_picture_url'),
                safe_str(row.get('host_neighbourhood'), 255),
                safe_int(row.get('host_listings_count'), 0),
                safe_int(row.get('host_total_listings_count'), 0),
                row.get('host_verifications'),
                safe_bool(row.get('host_has_profile_pic'), True),
                safe_bool(row.get('host_identity_verified')),
            )

    # Import hosts
    print(f"Importing {len(hosts)} hosts...")
    host_batch = list(hosts.values())
    for i in range(0, len(host_batch), 1000):
        batch = host_batch[i:i+1000]
        execute_values(cur, """
            INSERT INTO hosts (id, name, url, since, location, about, response_time,
                response_rate, acceptance_rate, is_superhost, thumbnail_url, picture_url,
                neighbourhood, listings_count, total_listings_count, verifications,
                has_profile_pic, identity_verified)
            VALUES %s ON CONFLICT (id) DO NOTHING
        """, batch)
        conn.commit()

    # Import listings
    print(f"Importing {len(rows)} listings...")
    count = 0
    batch = []
    batch_size = 1000

    for row in tqdm(rows, desc="Listings"):
        batch.append((
            safe_int(row.get('id')),
            row.get('listing_url'),
            safe_int(row.get('scrape_id')),
            safe_date(row.get('last_scraped')),
            safe_str(row.get('source'), 100),
            row.get('name'),
            row.get('description'),
            row.get('neighborhood_overview'),
            row.get('picture_url'),
            safe_int(row.get('host_id')),
            safe_str(row.get('neighbourhood'), 255),
            safe_str(row.get('neighbourhood_cleansed'), 255),
            safe_str(row.get('neighbourhood_group_cleansed'), 255),
            safe_float(row.get('latitude')),
            safe_float(row.get('longitude')),
            safe_str(row.get('property_type'), 100),
            safe_str(row.get('room_type'), 50),
            safe_int(row.get('accommodates')),
            safe_float(row.get('bathrooms')),
            safe_str(row.get('bathrooms_text'), 100),
            safe_int(row.get('bedrooms')),
            safe_int(row.get('beds')),
            row.get('amenities'),
            safe_float(row.get('price')),
            safe_int(row.get('minimum_nights')),
            safe_int(row.get('maximum_nights')),
            safe_int(row.get('minimum_minimum_nights')),
            safe_int(row.get('maximum_minimum_nights')),
            safe_int(row.get('minimum_maximum_nights')),
            safe_int(row.get('maximum_maximum_nights')),
            safe_float(row.get('minimum_nights_avg_ntm')),
            safe_float(row.get('maximum_nights_avg_ntm')),
            safe_date(row.get('calendar_updated')),
            safe_bool(row.get('has_availability')),
            safe_int(row.get('availability_30')),
            safe_int(row.get('availability_60')),
            safe_int(row.get('availability_90')),
            safe_int(row.get('availability_365')),
            safe_date(row.get('calendar_last_scraped')),
            safe_int(row.get('number_of_reviews'), 0),
            safe_int(row.get('number_of_reviews_ltm'), 0),
            safe_int(row.get('number_of_reviews_l30d'), 0),
            safe_date(row.get('first_review')),
            safe_date(row.get('last_review')),
            safe_float(row.get('review_scores_rating')),
            safe_float(row.get('review_scores_accuracy')),
            safe_float(row.get('review_scores_cleanliness')),
            safe_float(row.get('review_scores_checkin')),
            safe_float(row.get('review_scores_communication')),
            safe_float(row.get('review_scores_location')),
            safe_float(row.get('review_scores_value')),
            row.get('license'),
            safe_bool(row.get('instant_bookable')),
            safe_int(row.get('calculated_host_listings_count')),
            safe_int(row.get('calculated_host_listings_count_entire_homes')),
            safe_int(row.get('calculated_host_listings_count_private_rooms')),
            safe_int(row.get('calculated_host_listings_count_shared_rooms')),
            safe_float(row.get('reviews_per_month')),
        ))

        if len(batch) >= batch_size:
            execute_values(cur, """
                INSERT INTO listings (id, listing_url, scrape_id, last_scraped, source, name,
                    description, neighborhood_overview, picture_url, host_id, neighbourhood,
                    neighbourhood_cleansed, neighbourhood_group_cleansed, latitude, longitude,
                    property_type, room_type, accommodates, bathrooms, bathrooms_text, bedrooms,
                    beds, amenities, price, minimum_nights, maximum_nights, minimum_minimum_nights,
                    maximum_minimum_nights, minimum_maximum_nights, maximum_maximum_nights,
                    minimum_nights_avg_ntm, maximum_nights_avg_ntm, calendar_updated, has_availability,
                    availability_30, availability_60, availability_90, availability_365,
                    calendar_last_scraped, number_of_reviews, number_of_reviews_ltm,
                    number_of_reviews_l30d, first_review, last_review, review_scores_rating,
                    review_scores_accuracy, review_scores_cleanliness, review_scores_checkin,
                    review_scores_communication, review_scores_location, review_scores_value,
                    license, instant_bookable, calculated_host_listings_count,
                    calculated_host_listings_count_entire_homes, calculated_host_listings_count_private_rooms,
                    calculated_host_listings_count_shared_rooms, reviews_per_month)
                VALUES %s ON CONFLICT (id) DO NOTHING
            """, batch)
            conn.commit()
            count += len(batch)
            batch = []

    if batch:
        execute_values(cur, """
            INSERT INTO listings (id, listing_url, scrape_id, last_scraped, source, name,
                description, neighborhood_overview, picture_url, host_id, neighbourhood,
                neighbourhood_cleansed, neighbourhood_group_cleansed, latitude, longitude,
                property_type, room_type, accommodates, bathrooms, bathrooms_text, bedrooms,
                beds, amenities, price, minimum_nights, maximum_nights, minimum_minimum_nights,
                maximum_minimum_nights, minimum_maximum_nights, maximum_maximum_nights,
                minimum_nights_avg_ntm, maximum_nights_avg_ntm, calendar_updated, has_availability,
                availability_30, availability_60, availability_90, availability_365,
                calendar_last_scraped, number_of_reviews, number_of_reviews_ltm,
                number_of_reviews_l30d, first_review, last_review, review_scores_rating,
                review_scores_accuracy, review_scores_cleanliness, review_scores_checkin,
                review_scores_communication, review_scores_location, review_scores_value,
                license, instant_bookable, calculated_host_listings_count,
                calculated_host_listings_count_entire_homes, calculated_host_listings_count_private_rooms,
                calculated_host_listings_count_shared_rooms, reviews_per_month)
            VALUES %s ON CONFLICT (id) DO NOTHING
        """, batch)
        conn.commit()
        count += len(batch)

    cur.close()
    print(f"Imported {count} listings")


def import_reviews(city_config: dict, conn):
    """Import reviews data."""
    url = f"{city_config['base_url']}/{city_config['date']}/data/reviews.csv.gz"
    content = download_file(url, "Reviews")
    if not content:
        print("Failed to download reviews data")
        return

    rows = parse_csv_gz(content)
    if not rows:
        return

    cur = conn.cursor()

    # Get valid listing IDs
    cur.execute("SELECT id FROM listings")
    valid_listings = set(row[0] for row in cur.fetchall())

    print(f"Importing reviews (filtering for {len(valid_listings)} valid listings)...")
    count = 0
    skipped = 0
    batch = []
    batch_size = 5000

    for row in tqdm(rows, desc="Reviews"):
        listing_id = safe_int(row.get('listing_id'))
        if listing_id not in valid_listings:
            skipped += 1
            continue

        batch.append((
            safe_int(row.get('id')),
            listing_id,
            safe_date(row.get('date')),
            safe_int(row.get('reviewer_id')),
            safe_str(row.get('reviewer_name'), 255),
            row.get('comments'),
        ))

        if len(batch) >= batch_size:
            execute_values(cur, """
                INSERT INTO reviews (id, listing_id, date, reviewer_id, reviewer_name, comments)
                VALUES %s ON CONFLICT (id) DO NOTHING
            """, batch)
            conn.commit()
            count += len(batch)
            batch = []

    if batch:
        execute_values(cur, """
            INSERT INTO reviews (id, listing_id, date, reviewer_id, reviewer_name, comments)
            VALUES %s ON CONFLICT (id) DO NOTHING
        """, batch)
        conn.commit()
        count += len(batch)

    cur.close()
    print(f"Imported {count} reviews (skipped {skipped})")


def import_calendar(city_config: dict, conn):
    """Import calendar data."""
    url = f"{city_config['base_url']}/{city_config['date']}/data/calendar.csv.gz"
    content = download_file(url, "Calendar")
    if not content:
        print("Failed to download calendar data")
        return

    rows = parse_csv_gz(content)
    if not rows:
        return

    cur = conn.cursor()

    # Get valid listing IDs
    cur.execute("SELECT id FROM listings")
    valid_listings = set(row[0] for row in cur.fetchall())

    print(f"Importing calendar (filtering for {len(valid_listings)} valid listings)...")
    count = 0
    skipped = 0
    batch = []
    batch_size = 10000

    for row in tqdm(rows, desc="Calendar"):
        listing_id = safe_int(row.get('listing_id'))
        if listing_id not in valid_listings:
            skipped += 1
            continue

        batch.append((
            listing_id,
            safe_date(row.get('date')),
            safe_bool(row.get('available')),
            safe_float(row.get('price')),
            safe_float(row.get('adjusted_price')),
            safe_int(row.get('minimum_nights')),
            safe_int(row.get('maximum_nights')),
        ))

        if len(batch) >= batch_size:
            execute_values(cur, """
                INSERT INTO calendar (listing_id, date, available, price, adjusted_price,
                    minimum_nights, maximum_nights)
                VALUES %s ON CONFLICT (listing_id, date) DO NOTHING
            """, batch)
            conn.commit()
            count += len(batch)
            batch = []

    if batch:
        execute_values(cur, """
            INSERT INTO calendar (listing_id, date, available, price, adjusted_price,
                minimum_nights, maximum_nights)
            VALUES %s ON CONFLICT (listing_id, date) DO NOTHING
        """, batch)
        conn.commit()
        count += len(batch)

    cur.close()
    print(f"Imported {count} calendar entries (skipped {skipped})")


def refresh_materialized_views(conn):
    """Refresh materialized views."""
    print("Refreshing materialized views...")
    cur = conn.cursor()
    cur.execute("REFRESH MATERIALIZED VIEW neighbourhood_stats")
    cur.execute("REFRESH MATERIALIZED VIEW host_stats")
    conn.commit()
    cur.close()


def print_stats(conn):
    """Print database statistics."""
    cur = conn.cursor()

    print("\n" + "="*50)
    print("DATABASE STATISTICS")
    print("="*50)

    tables = ['neighbourhoods', 'hosts', 'listings', 'reviews', 'calendar']
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"{table:15} {count:>15,} rows")

    # Database size
    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
    size = cur.fetchone()[0]
    print(f"\nDatabase size: {size}")

    # Some interesting stats
    cur.execute("SELECT AVG(price), MIN(price), MAX(price) FROM listings WHERE price > 0")
    avg_price, min_price, max_price = cur.fetchone()
    print(f"\nPrice range: ${min_price:.2f} - ${max_price:.2f} (avg: ${avg_price:.2f})")

    cur.execute("SELECT AVG(review_scores_rating) FROM listings WHERE review_scores_rating IS NOT NULL")
    avg_rating = cur.fetchone()[0]
    print(f"Average rating: {avg_rating:.2f}")

    cur.close()


def main():
    parser = argparse.ArgumentParser(description='Import Airbnb sample data')
    parser.add_argument('--city', choices=list(CITIES.keys()) + ['all'],
                        default='barcelona', help='City to import data from (use "all" for all cities)')
    parser.add_argument('--skip-calendar', action='store_true',
                        help='Skip importing calendar data (very large)')
    args = parser.parse_args()

    # Determine cities to import
    if args.city == 'all':
        cities_to_import = list(CITIES.keys())
    else:
        cities_to_import = [args.city]

    print(f"\n{'='*50}")
    print(f"Airbnb Sample Database Import")
    print(f"Cities: {', '.join(c.title() for c in cities_to_import)}")
    print(f"{'='*50}\n")

    # Create database
    print("Creating database...")
    create_database()

    # Connect and create schema
    conn = get_connection()
    print("Creating schema...")
    cur = conn.cursor()
    cur.execute(SCHEMA_SQL)
    conn.commit()
    cur.close()

    # Import data for each city
    for city in cities_to_import:
        city_config = CITIES[city]
        print(f"\n{'='*50}")
        print(f"Importing {city.title()}...")
        print(f"Data date: {city_config['date']}")
        print(f"{'='*50}\n")

        import_neighbourhoods(city_config, conn)
        import_listings(city_config, conn)
        import_reviews(city_config, conn)

        if not args.skip_calendar:
            import_calendar(city_config, conn)
        else:
            print("Skipping calendar import")

    # Refresh materialized views
    refresh_materialized_views(conn)

    # Analyze tables
    print("\nAnalyzing tables...")
    cur = conn.cursor()
    cur.execute("ANALYZE")
    conn.commit()
    cur.close()

    # Print stats
    print_stats(conn)

    conn.close()

    print("\n" + "="*50)
    print("IMPORT COMPLETE!")
    print(f"Database: {DB_CONFIG['database']}")
    print(f"Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
    print("="*50)


if __name__ == '__main__':
    main()
