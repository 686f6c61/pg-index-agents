#!/usr/bin/env python3
"""
PG Index Agents - Script de importacion Stack Overflow
https://github.com/686f6c61/pg-index-agents

Script all-in-one que descarga, descomprime e importa datos de Stack Exchange
en PostgreSQL. Ideal para desarrollo y testing rapido.

Este script automatiza todo el proceso:
    1. Descarga el archivo .7z de archive.org
    2. Descomprime los XML con p7zip
    3. Crea la base de datos y esquema
    4. Importa datos en batches con progress bar
    5. Crea indices para consultas comunes

Tamanos de muestra disponibles:
    - small: coffee.stackexchange (~5K posts)
    - medium: dba.stackexchange (~75K posts) - Recomendado
    - large: serverfault (~350K posts)

Tablas creadas:
    - users: Usuarios de Stack Exchange
    - posts: Preguntas y respuestas
    - comments: Comentarios en posts
    - votes: Votos de usuarios
    - badges: Insignias otorgadas
    - tags: Etiquetas de preguntas
    - post_links: Enlaces entre posts

Requisitos:
    - PostgreSQL 14+
    - p7zip-full (sudo apt install p7zip-full)
    - Python packages: psycopg2, requests, tqdm

Uso:
    python import_stackoverflow.py --sample-size medium

Autor: 686f6c61
Licencia: MIT
"""

import os
import sys
import argparse
import subprocess
import tempfile
import xml.etree.ElementTree as ET
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
    'database': os.getenv('DB_NAME', 'stackoverflow_sample'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', ''),
}

# Stack Exchange Data Dump URLs (using smaller sites for faster download)
# For full Stack Overflow, use the main archive, but it's 80GB+
DATA_SOURCES = {
    'small': {
        'name': 'Stack Exchange - Coffee',
        'url': 'https://archive.org/download/stackexchange/coffee.stackexchange.com.7z',
        'expected_posts': 5000,
    },
    'medium': {
        'name': 'Stack Exchange - Database Administrators',
        'url': 'https://archive.org/download/stackexchange/dba.stackexchange.com.7z',
        'expected_posts': 75000,
    },
    'large': {
        'name': 'Stack Exchange - Server Fault',
        'url': 'https://archive.org/download/stackexchange/serverfault.com.7z',
        'expected_posts': 350000,
    },
}

# SQL Schema
SCHEMA_SQL = """
-- Stack Overflow Sample Database Schema
-- Based on Stack Exchange Data Dump schema

DROP TABLE IF EXISTS post_links CASCADE;
DROP TABLE IF EXISTS comments CASCADE;
DROP TABLE IF EXISTS votes CASCADE;
DROP TABLE IF EXISTS badges CASCADE;
DROP TABLE IF EXISTS posts CASCADE;
DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS tags CASCADE;

-- Users table
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    reputation INTEGER NOT NULL DEFAULT 0,
    creation_date TIMESTAMP NOT NULL,
    display_name VARCHAR(255) NOT NULL,
    last_access_date TIMESTAMP,
    website_url TEXT,
    location VARCHAR(255),
    about_me TEXT,
    views INTEGER DEFAULT 0,
    up_votes INTEGER DEFAULT 0,
    down_votes INTEGER DEFAULT 0,
    profile_image_url TEXT,
    account_id INTEGER
);

-- Tags table
CREATE TABLE tags (
    id SERIAL PRIMARY KEY,
    tag_name VARCHAR(255) UNIQUE NOT NULL,
    count INTEGER DEFAULT 0,
    excerpt_post_id INTEGER,
    wiki_post_id INTEGER
);

-- Posts table (questions and answers)
-- Note: FKs removed to handle deleted users in Stack Exchange dumps
CREATE TABLE posts (
    id INTEGER PRIMARY KEY,
    post_type_id INTEGER NOT NULL,  -- 1 = Question, 2 = Answer
    accepted_answer_id INTEGER,
    parent_id INTEGER,
    creation_date TIMESTAMP NOT NULL,
    deletion_date TIMESTAMP,
    score INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    body TEXT,
    owner_user_id INTEGER,  -- No FK - users may be deleted
    owner_display_name VARCHAR(255),
    last_editor_user_id INTEGER,
    last_editor_display_name VARCHAR(255),
    last_edit_date TIMESTAMP,
    last_activity_date TIMESTAMP,
    title VARCHAR(512),
    tags TEXT,
    answer_count INTEGER DEFAULT 0,
    comment_count INTEGER DEFAULT 0,
    favorite_count INTEGER DEFAULT 0,
    closed_date TIMESTAMP,
    community_owned_date TIMESTAMP,
    content_license VARCHAR(50)
);

-- Comments table (FKs removed for bulk import)
CREATE TABLE comments (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL,
    score INTEGER DEFAULT 0,
    text TEXT NOT NULL,
    creation_date TIMESTAMP NOT NULL,
    user_display_name VARCHAR(255),
    user_id INTEGER,
    content_license VARCHAR(50)
);

-- Votes table (FKs removed for bulk import)
CREATE TABLE votes (
    id INTEGER PRIMARY KEY,
    post_id INTEGER NOT NULL,
    vote_type_id INTEGER NOT NULL,  -- 1=Accepted, 2=Upvote, 3=Downvote, etc.
    user_id INTEGER,
    creation_date TIMESTAMP NOT NULL,
    bounty_amount INTEGER
);

-- Badges table (FKs removed for bulk import)
CREATE TABLE badges (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL,
    name VARCHAR(255) NOT NULL,
    date TIMESTAMP NOT NULL,
    class INTEGER NOT NULL,  -- 1=Gold, 2=Silver, 3=Bronze
    tag_based BOOLEAN DEFAULT FALSE
);

-- Post links table (FKs removed for bulk import)
CREATE TABLE post_links (
    id INTEGER PRIMARY KEY,
    creation_date TIMESTAMP NOT NULL,
    post_id INTEGER NOT NULL,
    related_post_id INTEGER NOT NULL,
    link_type_id INTEGER NOT NULL  -- 1=Linked, 3=Duplicate
);

-- Create indexes for common query patterns
CREATE INDEX idx_posts_owner ON posts(owner_user_id);
CREATE INDEX idx_posts_creation ON posts(creation_date);
CREATE INDEX idx_posts_type ON posts(post_type_id);
CREATE INDEX idx_posts_parent ON posts(parent_id);
CREATE INDEX idx_posts_score ON posts(score DESC);

CREATE INDEX idx_comments_post ON comments(post_id);
CREATE INDEX idx_comments_user ON comments(user_id);
CREATE INDEX idx_comments_creation ON comments(creation_date);

CREATE INDEX idx_votes_post ON votes(post_id);
CREATE INDEX idx_votes_user ON votes(user_id);
CREATE INDEX idx_votes_type ON votes(vote_type_id);

CREATE INDEX idx_badges_user ON badges(user_id);
CREATE INDEX idx_badges_name ON badges(name);

CREATE INDEX idx_post_links_post ON post_links(post_id);
CREATE INDEX idx_post_links_related ON post_links(related_post_id);

CREATE INDEX idx_users_reputation ON users(reputation DESC);
CREATE INDEX idx_users_creation ON users(creation_date);

-- Note: fk_posts_parent constraint will be added after data import
-- ALTER TABLE posts ADD CONSTRAINT fk_posts_parent
--     FOREIGN KEY (parent_id) REFERENCES posts(id) ON DELETE SET NULL;

-- Create text search indexes for full-text search demo
CREATE INDEX idx_posts_title_fts ON posts USING gin(to_tsvector('english', COALESCE(title, '')));
CREATE INDEX idx_posts_body_fts ON posts USING gin(to_tsvector('english', COALESCE(body, '')));
"""


def download_file(url: str, dest: Path, desc: str = "Downloading") -> bool:
    """Download a file with progress bar."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()
        total_size = int(response.headers.get('content-length', 0))

        with open(dest, 'wb') as f:
            with tqdm(total=total_size, unit='B', unit_scale=True, desc=desc) as pbar:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    pbar.update(len(chunk))
        return True
    except Exception as e:
        print(f"Error downloading: {e}")
        return False


def extract_7z(archive: Path, dest: Path) -> bool:
    """Extract 7z archive."""
    try:
        subprocess.run(['7z', 'x', str(archive), f'-o{dest}', '-y'], check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error extracting: {e}")
        return False
    except FileNotFoundError:
        print("Error: 7z not found. Install with: sudo apt install p7zip-full")
        return False


def parse_xml_file(filepath: Path, tag: str, limit: int = None):
    """Parse XML file and yield row dictionaries."""
    count = 0
    try:
        for event, elem in ET.iterparse(filepath, events=['end']):
            if elem.tag == 'row':
                yield dict(elem.attrib)
                count += 1
                if limit and count >= limit:
                    break
                elem.clear()
    except Exception as e:
        print(f"Error parsing {filepath}: {e}")


def safe_int(value, default=None):
    """Safely convert to int."""
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_datetime(value, default=None):
    """Safely convert to datetime."""
    if value is None:
        return default
    try:
        return datetime.fromisoformat(value.replace('T', ' ').split('.')[0])
    except (ValueError, TypeError):
        return default


def safe_bool(value, default=False):
    """Safely convert to bool."""
    if value is None:
        return default
    return str(value).lower() in ('true', '1', 'yes')


def create_database():
    """Create the database if it doesn't exist."""
    # Connect to default database to create our target database
    conn = psycopg2.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        database='postgres',
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Check if database exists
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


def import_users(data_dir: Path, conn, limit: int = None):
    """Import users from XML."""
    users_file = data_dir / 'Users.xml'
    if not users_file.exists():
        print("Users.xml not found, skipping...")
        return

    print("Importing users...")
    cur = conn.cursor()

    batch = []
    batch_size = 1000
    count = 0

    for row in tqdm(parse_xml_file(users_file, 'row', limit), desc="Users"):
        batch.append((
            safe_int(row.get('Id')),
            safe_int(row.get('Reputation'), 0),
            safe_datetime(row.get('CreationDate'), datetime.now()),
            row.get('DisplayName', 'Unknown')[:255],
            safe_datetime(row.get('LastAccessDate')),
            row.get('WebsiteUrl'),
            row.get('Location', '')[:255] if row.get('Location') else None,
            row.get('AboutMe'),
            safe_int(row.get('Views'), 0),
            safe_int(row.get('UpVotes'), 0),
            safe_int(row.get('DownVotes'), 0),
            row.get('ProfileImageUrl'),
            safe_int(row.get('AccountId')),
        ))

        if len(batch) >= batch_size:
            execute_values(cur, """
                INSERT INTO users (id, reputation, creation_date, display_name, last_access_date,
                    website_url, location, about_me, views, up_votes, down_votes,
                    profile_image_url, account_id)
                VALUES %s ON CONFLICT (id) DO NOTHING
            """, batch)
            conn.commit()
            count += len(batch)
            batch = []

    if batch:
        execute_values(cur, """
            INSERT INTO users (id, reputation, creation_date, display_name, last_access_date,
                website_url, location, about_me, views, up_votes, down_votes,
                profile_image_url, account_id)
            VALUES %s ON CONFLICT (id) DO NOTHING
        """, batch)
        conn.commit()
        count += len(batch)

    cur.close()
    print(f"Imported {count} users")


def import_posts(data_dir: Path, conn, limit: int = None):
    """Import posts from XML."""
    posts_file = data_dir / 'Posts.xml'
    if not posts_file.exists():
        print("Posts.xml not found, skipping...")
        return

    print("Importing posts...")
    cur = conn.cursor()

    batch = []
    batch_size = 1000
    count = 0

    for row in tqdm(parse_xml_file(posts_file, 'row', limit), desc="Posts"):
        batch.append((
            safe_int(row.get('Id')),
            safe_int(row.get('PostTypeId'), 1),
            safe_int(row.get('AcceptedAnswerId')),
            safe_int(row.get('ParentId')),
            safe_datetime(row.get('CreationDate'), datetime.now()),
            safe_datetime(row.get('DeletionDate')),
            safe_int(row.get('Score'), 0),
            safe_int(row.get('ViewCount'), 0),
            row.get('Body'),
            safe_int(row.get('OwnerUserId')),
            row.get('OwnerDisplayName', '')[:255] if row.get('OwnerDisplayName') else None,
            safe_int(row.get('LastEditorUserId')),
            row.get('LastEditorDisplayName', '')[:255] if row.get('LastEditorDisplayName') else None,
            safe_datetime(row.get('LastEditDate')),
            safe_datetime(row.get('LastActivityDate')),
            row.get('Title', '')[:512] if row.get('Title') else None,
            row.get('Tags'),
            safe_int(row.get('AnswerCount'), 0),
            safe_int(row.get('CommentCount'), 0),
            safe_int(row.get('FavoriteCount'), 0),
            safe_datetime(row.get('ClosedDate')),
            safe_datetime(row.get('CommunityOwnedDate')),
            row.get('ContentLicense', '')[:50] if row.get('ContentLicense') else None,
        ))

        if len(batch) >= batch_size:
            execute_values(cur, """
                INSERT INTO posts (id, post_type_id, accepted_answer_id, parent_id, creation_date,
                    deletion_date, score, view_count, body, owner_user_id, owner_display_name,
                    last_editor_user_id, last_editor_display_name, last_edit_date, last_activity_date,
                    title, tags, answer_count, comment_count, favorite_count, closed_date,
                    community_owned_date, content_license)
                VALUES %s ON CONFLICT (id) DO NOTHING
            """, batch)
            conn.commit()
            count += len(batch)
            batch = []

    if batch:
        execute_values(cur, """
            INSERT INTO posts (id, post_type_id, accepted_answer_id, parent_id, creation_date,
                deletion_date, score, view_count, body, owner_user_id, owner_display_name,
                last_editor_user_id, last_editor_display_name, last_edit_date, last_activity_date,
                title, tags, answer_count, comment_count, favorite_count, closed_date,
                community_owned_date, content_license)
            VALUES %s ON CONFLICT (id) DO NOTHING
        """, batch)
        conn.commit()
        count += len(batch)

    cur.close()
    print(f"Imported {count} posts")


def import_comments(data_dir: Path, conn, limit: int = None):
    """Import comments from XML."""
    comments_file = data_dir / 'Comments.xml'
    if not comments_file.exists():
        print("Comments.xml not found, skipping...")
        return

    print("Importing comments...")
    cur = conn.cursor()

    batch = []
    batch_size = 1000
    count = 0
    skipped = 0

    # Get valid post IDs
    cur.execute("SELECT id FROM posts")
    valid_post_ids = set(row[0] for row in cur.fetchall())

    for row in tqdm(parse_xml_file(comments_file, 'row', limit), desc="Comments"):
        post_id = safe_int(row.get('PostId'))
        if post_id not in valid_post_ids:
            skipped += 1
            continue

        batch.append((
            safe_int(row.get('Id')),
            post_id,
            safe_int(row.get('Score'), 0),
            row.get('Text', ''),
            safe_datetime(row.get('CreationDate'), datetime.now()),
            row.get('UserDisplayName', '')[:255] if row.get('UserDisplayName') else None,
            safe_int(row.get('UserId')),
            row.get('ContentLicense', '')[:50] if row.get('ContentLicense') else None,
        ))

        if len(batch) >= batch_size:
            execute_values(cur, """
                INSERT INTO comments (id, post_id, score, text, creation_date,
                    user_display_name, user_id, content_license)
                VALUES %s ON CONFLICT (id) DO NOTHING
            """, batch)
            conn.commit()
            count += len(batch)
            batch = []

    if batch:
        execute_values(cur, """
            INSERT INTO comments (id, post_id, score, text, creation_date,
                user_display_name, user_id, content_license)
            VALUES %s ON CONFLICT (id) DO NOTHING
        """, batch)
        conn.commit()
        count += len(batch)

    cur.close()
    print(f"Imported {count} comments (skipped {skipped} with invalid post_id)")


def import_votes(data_dir: Path, conn, limit: int = None):
    """Import votes from XML."""
    votes_file = data_dir / 'Votes.xml'
    if not votes_file.exists():
        print("Votes.xml not found, skipping...")
        return

    print("Importing votes...")
    cur = conn.cursor()

    batch = []
    batch_size = 1000
    count = 0
    skipped = 0

    # Get valid post IDs
    cur.execute("SELECT id FROM posts")
    valid_post_ids = set(row[0] for row in cur.fetchall())

    for row in tqdm(parse_xml_file(votes_file, 'row', limit), desc="Votes"):
        post_id = safe_int(row.get('PostId'))
        if post_id not in valid_post_ids:
            skipped += 1
            continue

        batch.append((
            safe_int(row.get('Id')),
            post_id,
            safe_int(row.get('VoteTypeId'), 2),
            safe_int(row.get('UserId')),
            safe_datetime(row.get('CreationDate'), datetime.now()),
            safe_int(row.get('BountyAmount')),
        ))

        if len(batch) >= batch_size:
            execute_values(cur, """
                INSERT INTO votes (id, post_id, vote_type_id, user_id, creation_date, bounty_amount)
                VALUES %s ON CONFLICT (id) DO NOTHING
            """, batch)
            conn.commit()
            count += len(batch)
            batch = []

    if batch:
        execute_values(cur, """
            INSERT INTO votes (id, post_id, vote_type_id, user_id, creation_date, bounty_amount)
            VALUES %s ON CONFLICT (id) DO NOTHING
        """, batch)
        conn.commit()
        count += len(batch)

    cur.close()
    print(f"Imported {count} votes (skipped {skipped} with invalid post_id)")


def import_badges(data_dir: Path, conn, limit: int = None):
    """Import badges from XML."""
    badges_file = data_dir / 'Badges.xml'
    if not badges_file.exists():
        print("Badges.xml not found, skipping...")
        return

    print("Importing badges...")
    cur = conn.cursor()

    batch = []
    batch_size = 1000
    count = 0
    skipped = 0

    # Get valid user IDs
    cur.execute("SELECT id FROM users")
    valid_user_ids = set(row[0] for row in cur.fetchall())

    for row in tqdm(parse_xml_file(badges_file, 'row', limit), desc="Badges"):
        user_id = safe_int(row.get('UserId'))
        if user_id not in valid_user_ids:
            skipped += 1
            continue

        batch.append((
            safe_int(row.get('Id')),
            user_id,
            row.get('Name', 'Unknown')[:255],
            safe_datetime(row.get('Date'), datetime.now()),
            safe_int(row.get('Class'), 3),
            safe_bool(row.get('TagBased')),
        ))

        if len(batch) >= batch_size:
            execute_values(cur, """
                INSERT INTO badges (id, user_id, name, date, class, tag_based)
                VALUES %s ON CONFLICT (id) DO NOTHING
            """, batch)
            conn.commit()
            count += len(batch)
            batch = []

    if batch:
        execute_values(cur, """
            INSERT INTO badges (id, user_id, name, date, class, tag_based)
            VALUES %s ON CONFLICT (id) DO NOTHING
        """, batch)
        conn.commit()
        count += len(batch)

    cur.close()
    print(f"Imported {count} badges (skipped {skipped} with invalid user_id)")


def import_tags(data_dir: Path, conn, limit: int = None):
    """Import tags from XML."""
    tags_file = data_dir / 'Tags.xml'
    if not tags_file.exists():
        print("Tags.xml not found, skipping...")
        return

    print("Importing tags...")
    cur = conn.cursor()

    batch = []
    batch_size = 1000
    count = 0

    for row in tqdm(parse_xml_file(tags_file, 'row', limit), desc="Tags"):
        batch.append((
            row.get('TagName', 'unknown')[:255],
            safe_int(row.get('Count'), 0),
            safe_int(row.get('ExcerptPostId')),
            safe_int(row.get('WikiPostId')),
        ))

        if len(batch) >= batch_size:
            execute_values(cur, """
                INSERT INTO tags (tag_name, count, excerpt_post_id, wiki_post_id)
                VALUES %s ON CONFLICT (tag_name) DO NOTHING
            """, batch)
            conn.commit()
            count += len(batch)
            batch = []

    if batch:
        execute_values(cur, """
            INSERT INTO tags (tag_name, count, excerpt_post_id, wiki_post_id)
            VALUES %s ON CONFLICT (tag_name) DO NOTHING
        """, batch)
        conn.commit()
        count += len(batch)

    cur.close()
    print(f"Imported {count} tags")


def import_post_links(data_dir: Path, conn, limit: int = None):
    """Import post links from XML."""
    links_file = data_dir / 'PostLinks.xml'
    if not links_file.exists():
        print("PostLinks.xml not found, skipping...")
        return

    print("Importing post links...")
    cur = conn.cursor()

    batch = []
    batch_size = 1000
    count = 0
    skipped = 0

    # Get valid post IDs
    cur.execute("SELECT id FROM posts")
    valid_post_ids = set(row[0] for row in cur.fetchall())

    for row in tqdm(parse_xml_file(links_file, 'row', limit), desc="Post Links"):
        post_id = safe_int(row.get('PostId'))
        related_post_id = safe_int(row.get('RelatedPostId'))

        if post_id not in valid_post_ids or related_post_id not in valid_post_ids:
            skipped += 1
            continue

        batch.append((
            safe_int(row.get('Id')),
            safe_datetime(row.get('CreationDate'), datetime.now()),
            post_id,
            related_post_id,
            safe_int(row.get('LinkTypeId'), 1),
        ))

        if len(batch) >= batch_size:
            execute_values(cur, """
                INSERT INTO post_links (id, creation_date, post_id, related_post_id, link_type_id)
                VALUES %s ON CONFLICT (id) DO NOTHING
            """, batch)
            conn.commit()
            count += len(batch)
            batch = []

    if batch:
        execute_values(cur, """
            INSERT INTO post_links (id, creation_date, post_id, related_post_id, link_type_id)
            VALUES %s ON CONFLICT (id) DO NOTHING
        """, batch)
        conn.commit()
        count += len(batch)

    cur.close()
    print(f"Imported {count} post links (skipped {skipped} with invalid post_id)")


def print_stats(conn):
    """Print database statistics."""
    cur = conn.cursor()

    print("\n" + "="*50)
    print("DATABASE STATISTICS")
    print("="*50)

    tables = ['users', 'posts', 'comments', 'votes', 'badges', 'tags', 'post_links']
    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]
        print(f"{table:15} {count:>10,} rows")

    # Database size
    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
    size = cur.fetchone()[0]
    print(f"\nDatabase size: {size}")

    cur.close()


def main():
    parser = argparse.ArgumentParser(description='Import Stack Overflow sample data')
    parser.add_argument('--sample-size', choices=['small', 'medium', 'large'],
                        default='medium', help='Size of sample to import')
    parser.add_argument('--skip-download', action='store_true',
                        help='Skip download if data already exists')
    args = parser.parse_args()

    source = DATA_SOURCES[args.sample_size]
    print(f"\n{'='*50}")
    print(f"Stack Overflow Sample Database Import")
    print(f"Source: {source['name']}")
    print(f"Expected posts: ~{source['expected_posts']:,}")
    print(f"{'='*50}\n")

    # Create temp directory for data
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        archive_path = tmpdir / 'data.7z'
        extract_path = tmpdir / 'extracted'
        extract_path.mkdir()

        # Check for existing extracted data
        data_dir = None
        if args.skip_download:
            # Look for existing data in common locations
            possible_paths = [
                Path('/tmp/stackoverflow_data'),
                Path.home() / 'stackoverflow_data',
            ]
            for p in possible_paths:
                if p.exists() and (p / 'Posts.xml').exists():
                    data_dir = p
                    print(f"Using existing data from: {data_dir}")
                    break

        if not data_dir:
            # Download data
            print(f"Downloading data from {source['url']}...")
            if not download_file(source['url'], archive_path, "Downloading"):
                print("Failed to download data")
                sys.exit(1)

            # Extract data
            print("Extracting archive...")
            if not extract_7z(archive_path, extract_path):
                print("Failed to extract archive")
                sys.exit(1)

            # Find the extracted data directory
            for item in extract_path.iterdir():
                if item.is_dir():
                    data_dir = item
                    break
            if not data_dir:
                data_dir = extract_path

        print(f"\nData directory: {data_dir}")
        print("Files found:", list(data_dir.glob('*.xml')))

        # Create database
        print("\nCreating database...")
        create_database()

        # Connect and create schema
        conn = get_connection()
        print("Creating schema...")
        cur = conn.cursor()
        cur.execute(SCHEMA_SQL)
        conn.commit()
        cur.close()

        # Import data
        print("\nImporting data...")
        import_users(data_dir, conn)
        import_posts(data_dir, conn)
        import_comments(data_dir, conn)
        import_votes(data_dir, conn)
        import_badges(data_dir, conn)
        import_tags(data_dir, conn)
        import_post_links(data_dir, conn)

        # Analyze tables for better query planning
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
