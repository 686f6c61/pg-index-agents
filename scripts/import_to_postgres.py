#!/usr/bin/env python3
"""
PG Index Agents - Script de importacion XML a PostgreSQL
https://github.com/686f6c61/pg-index-agents

Script para importar archivos XML de Stack Exchange previamente descargados
en una base de datos PostgreSQL. Complementa a download_stackexchange.py.

Flujo de trabajo:
    1. Ejecutar download_stackexchange.py para obtener los XML
    2. Ejecutar este script para cargar en PostgreSQL

Archivos XML soportados:
    - Users.xml: Usuarios registrados
    - Posts.xml: Preguntas y respuestas
    - Comments.xml: Comentarios en posts
    - Votes.xml: Votos de usuarios
    - Badges.xml: Insignias otorgadas
    - Tags.xml: Etiquetas de preguntas

El script:
    - Crea la base de datos si no existe
    - Genera el esquema de tablas
    - Importa datos en batches de 10K rows
    - Crea indices para rendimiento
    - Ejecuta ANALYZE para estadisticas

Directorio de datos: {proyecto}/data/*.xml

Uso:
    python import_to_postgres.py

Variables de entorno:
    - PG_TARGET_DATABASE: Nombre de la base de datos (default: stackexchange)
    - PG_TARGET_USER: Usuario PostgreSQL (default: r)

Autor: 686f6c61
Licencia: MIT
"""

import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values
import time

# Configuration - Override via environment variables
DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("PG_TARGET_DATABASE", "stackexchange"),
    "user": os.getenv("PG_TARGET_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

DATA_DIR = Path(__file__).parent.parent / "data"
BATCH_SIZE = 10000  # Rows per batch insert


def get_connection(db_config=None, database=None):
    """Get a database connection."""
    config = db_config or DB_CONFIG.copy()
    if database:
        config["database"] = database
    return psycopg2.connect(**config)


def create_database():
    """Create the stackexchange database if it doesn't exist."""
    print("[DB] Checking/creating database...")

    # Connect to postgres database to create our database
    config = DB_CONFIG.copy()
    config["database"] = "postgres"

    conn = get_connection(config)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute(
        "SELECT 1 FROM pg_database WHERE datname = %s",
        (DB_CONFIG["database"],)
    )

    if not cur.fetchone():
        print(f"[DB] Creating database '{DB_CONFIG['database']}'...")
        cur.execute(f'CREATE DATABASE {DB_CONFIG["database"]}')
        print("[DB] Database created")
    else:
        print("[DB] Database already exists")

    cur.close()
    conn.close()


def create_schema():
    """Create the database schema for Stack Exchange data."""
    print("[SCHEMA] Creating tables...")

    conn = get_connection()
    cur = conn.cursor()

    # Drop existing tables (for clean import)
    cur.execute("""
        DROP TABLE IF EXISTS post_links CASCADE;
        DROP TABLE IF EXISTS post_history CASCADE;
        DROP TABLE IF EXISTS comments CASCADE;
        DROP TABLE IF EXISTS votes CASCADE;
        DROP TABLE IF EXISTS badges CASCADE;
        DROP TABLE IF EXISTS tags CASCADE;
        DROP TABLE IF EXISTS posts CASCADE;
        DROP TABLE IF EXISTS users CASCADE;
    """)

    # Users table
    cur.execute("""
        CREATE TABLE users (
            id INTEGER PRIMARY KEY,
            reputation INTEGER,
            creation_date TIMESTAMP,
            display_name VARCHAR(255),
            last_access_date TIMESTAMP,
            website_url TEXT,
            location VARCHAR(512),
            about_me TEXT,
            views INTEGER,
            up_votes INTEGER,
            down_votes INTEGER,
            profile_image_url TEXT,
            account_id INTEGER
        )
    """)

    # Posts table (questions and answers)
    cur.execute("""
        CREATE TABLE posts (
            id INTEGER PRIMARY KEY,
            post_type_id SMALLINT,
            accepted_answer_id INTEGER,
            parent_id INTEGER,
            creation_date TIMESTAMP,
            deletion_date TIMESTAMP,
            score INTEGER,
            view_count INTEGER,
            body TEXT,
            owner_user_id INTEGER,
            owner_display_name VARCHAR(255),
            last_editor_user_id INTEGER,
            last_editor_display_name VARCHAR(255),
            last_edit_date TIMESTAMP,
            last_activity_date TIMESTAMP,
            title TEXT,
            tags TEXT,
            answer_count INTEGER,
            comment_count INTEGER,
            favorite_count INTEGER,
            closed_date TIMESTAMP,
            community_owned_date TIMESTAMP,
            content_license VARCHAR(50)
        )
    """)

    # Comments table
    cur.execute("""
        CREATE TABLE comments (
            id INTEGER PRIMARY KEY,
            post_id INTEGER,
            score INTEGER,
            text TEXT,
            creation_date TIMESTAMP,
            user_display_name VARCHAR(255),
            user_id INTEGER,
            content_license VARCHAR(50)
        )
    """)

    # Votes table
    cur.execute("""
        CREATE TABLE votes (
            id INTEGER PRIMARY KEY,
            post_id INTEGER,
            vote_type_id SMALLINT,
            user_id INTEGER,
            creation_date TIMESTAMP,
            bounty_amount INTEGER
        )
    """)

    # Badges table
    cur.execute("""
        CREATE TABLE badges (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            name VARCHAR(255),
            date TIMESTAMP,
            class SMALLINT,
            tag_based BOOLEAN
        )
    """)

    # Tags table
    cur.execute("""
        CREATE TABLE tags (
            id INTEGER PRIMARY KEY,
            tag_name VARCHAR(255),
            count INTEGER,
            excerpt_post_id INTEGER,
            wiki_post_id INTEGER
        )
    """)

    # PostLinks table
    cur.execute("""
        CREATE TABLE post_links (
            id INTEGER PRIMARY KEY,
            creation_date TIMESTAMP,
            post_id INTEGER,
            related_post_id INTEGER,
            link_type_id SMALLINT
        )
    """)

    conn.commit()
    print("[SCHEMA] Tables created")

    cur.close()
    conn.close()


def parse_date(date_str):
    """Parse a date string from Stack Exchange XML."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except:
        return None


def parse_int(val):
    """Parse an integer, returning None if invalid."""
    if val is None:
        return None
    try:
        return int(val)
    except:
        return None


def parse_bool(val):
    """Parse a boolean from string."""
    if val is None:
        return None
    return val.lower() in ("true", "1", "yes")


def import_users(xml_file: Path):
    """Import users from XML file."""
    print(f"\n[IMPORT] Importing users from {xml_file.name}...")

    conn = get_connection()
    cur = conn.cursor()

    batch = []
    count = 0
    start_time = time.time()

    # Use iterparse for memory efficiency
    context = ET.iterparse(str(xml_file), events=("end",))

    for event, elem in context:
        if elem.tag == "row":
            row = (
                parse_int(elem.get("Id")),
                parse_int(elem.get("Reputation")),
                parse_date(elem.get("CreationDate")),
                elem.get("DisplayName"),
                parse_date(elem.get("LastAccessDate")),
                elem.get("WebsiteUrl"),
                elem.get("Location"),
                elem.get("AboutMe"),
                parse_int(elem.get("Views")),
                parse_int(elem.get("UpVotes")),
                parse_int(elem.get("DownVotes")),
                elem.get("ProfileImageUrl"),
                parse_int(elem.get("AccountId")),
            )
            batch.append(row)
            count += 1

            if len(batch) >= BATCH_SIZE:
                execute_values(
                    cur,
                    """INSERT INTO users (id, reputation, creation_date, display_name,
                       last_access_date, website_url, location, about_me, views,
                       up_votes, down_votes, profile_image_url, account_id)
                       VALUES %s ON CONFLICT (id) DO NOTHING""",
                    batch
                )
                conn.commit()
                batch = []
                elapsed = time.time() - start_time
                rate = count / elapsed if elapsed > 0 else 0
                print(f"\r  Imported {count:,} users ({rate:.0f}/s)...", end="")

            elem.clear()

    # Insert remaining batch
    if batch:
        execute_values(
            cur,
            """INSERT INTO users (id, reputation, creation_date, display_name,
               last_access_date, website_url, location, about_me, views,
               up_votes, down_votes, profile_image_url, account_id)
               VALUES %s ON CONFLICT (id) DO NOTHING""",
            batch
        )
        conn.commit()

    elapsed = time.time() - start_time
    print(f"\n  Done! Imported {count:,} users in {elapsed:.1f}s")

    cur.close()
    conn.close()
    return count


def import_posts(xml_file: Path):
    """Import posts from XML file."""
    print(f"\n[IMPORT] Importing posts from {xml_file.name}...")

    conn = get_connection()
    cur = conn.cursor()

    batch = []
    count = 0
    start_time = time.time()

    context = ET.iterparse(str(xml_file), events=("end",))

    for event, elem in context:
        if elem.tag == "row":
            row = (
                parse_int(elem.get("Id")),
                parse_int(elem.get("PostTypeId")),
                parse_int(elem.get("AcceptedAnswerId")),
                parse_int(elem.get("ParentId")),
                parse_date(elem.get("CreationDate")),
                parse_date(elem.get("DeletionDate")),
                parse_int(elem.get("Score")),
                parse_int(elem.get("ViewCount")),
                elem.get("Body"),
                parse_int(elem.get("OwnerUserId")),
                elem.get("OwnerDisplayName"),
                parse_int(elem.get("LastEditorUserId")),
                elem.get("LastEditorDisplayName"),
                parse_date(elem.get("LastEditDate")),
                parse_date(elem.get("LastActivityDate")),
                elem.get("Title"),
                elem.get("Tags"),
                parse_int(elem.get("AnswerCount")),
                parse_int(elem.get("CommentCount")),
                parse_int(elem.get("FavoriteCount")),
                parse_date(elem.get("ClosedDate")),
                parse_date(elem.get("CommunityOwnedDate")),
                elem.get("ContentLicense"),
            )
            batch.append(row)
            count += 1

            if len(batch) >= BATCH_SIZE:
                execute_values(
                    cur,
                    """INSERT INTO posts (id, post_type_id, accepted_answer_id, parent_id,
                       creation_date, deletion_date, score, view_count, body,
                       owner_user_id, owner_display_name, last_editor_user_id,
                       last_editor_display_name, last_edit_date, last_activity_date,
                       title, tags, answer_count, comment_count, favorite_count,
                       closed_date, community_owned_date, content_license)
                       VALUES %s ON CONFLICT (id) DO NOTHING""",
                    batch
                )
                conn.commit()
                batch = []
                elapsed = time.time() - start_time
                rate = count / elapsed if elapsed > 0 else 0
                print(f"\r  Imported {count:,} posts ({rate:.0f}/s)...", end="")

            elem.clear()

    if batch:
        execute_values(
            cur,
            """INSERT INTO posts (id, post_type_id, accepted_answer_id, parent_id,
               creation_date, deletion_date, score, view_count, body,
               owner_user_id, owner_display_name, last_editor_user_id,
               last_editor_display_name, last_edit_date, last_activity_date,
               title, tags, answer_count, comment_count, favorite_count,
               closed_date, community_owned_date, content_license)
               VALUES %s ON CONFLICT (id) DO NOTHING""",
            batch
        )
        conn.commit()

    elapsed = time.time() - start_time
    print(f"\n  Done! Imported {count:,} posts in {elapsed:.1f}s")

    cur.close()
    conn.close()
    return count


def import_comments(xml_file: Path):
    """Import comments from XML file."""
    print(f"\n[IMPORT] Importing comments from {xml_file.name}...")

    conn = get_connection()
    cur = conn.cursor()

    batch = []
    count = 0
    start_time = time.time()

    context = ET.iterparse(str(xml_file), events=("end",))

    for event, elem in context:
        if elem.tag == "row":
            row = (
                parse_int(elem.get("Id")),
                parse_int(elem.get("PostId")),
                parse_int(elem.get("Score")),
                elem.get("Text"),
                parse_date(elem.get("CreationDate")),
                elem.get("UserDisplayName"),
                parse_int(elem.get("UserId")),
                elem.get("ContentLicense"),
            )
            batch.append(row)
            count += 1

            if len(batch) >= BATCH_SIZE:
                execute_values(
                    cur,
                    """INSERT INTO comments (id, post_id, score, text, creation_date,
                       user_display_name, user_id, content_license)
                       VALUES %s ON CONFLICT (id) DO NOTHING""",
                    batch
                )
                conn.commit()
                batch = []
                elapsed = time.time() - start_time
                rate = count / elapsed if elapsed > 0 else 0
                print(f"\r  Imported {count:,} comments ({rate:.0f}/s)...", end="")

            elem.clear()

    if batch:
        execute_values(
            cur,
            """INSERT INTO comments (id, post_id, score, text, creation_date,
               user_display_name, user_id, content_license)
               VALUES %s ON CONFLICT (id) DO NOTHING""",
            batch
        )
        conn.commit()

    elapsed = time.time() - start_time
    print(f"\n  Done! Imported {count:,} comments in {elapsed:.1f}s")

    cur.close()
    conn.close()
    return count


def import_votes(xml_file: Path):
    """Import votes from XML file."""
    print(f"\n[IMPORT] Importing votes from {xml_file.name}...")

    conn = get_connection()
    cur = conn.cursor()

    batch = []
    count = 0
    start_time = time.time()

    context = ET.iterparse(str(xml_file), events=("end",))

    for event, elem in context:
        if elem.tag == "row":
            row = (
                parse_int(elem.get("Id")),
                parse_int(elem.get("PostId")),
                parse_int(elem.get("VoteTypeId")),
                parse_int(elem.get("UserId")),
                parse_date(elem.get("CreationDate")),
                parse_int(elem.get("BountyAmount")),
            )
            batch.append(row)
            count += 1

            if len(batch) >= BATCH_SIZE:
                execute_values(
                    cur,
                    """INSERT INTO votes (id, post_id, vote_type_id, user_id,
                       creation_date, bounty_amount)
                       VALUES %s ON CONFLICT (id) DO NOTHING""",
                    batch
                )
                conn.commit()
                batch = []
                elapsed = time.time() - start_time
                rate = count / elapsed if elapsed > 0 else 0
                print(f"\r  Imported {count:,} votes ({rate:.0f}/s)...", end="")

            elem.clear()

    if batch:
        execute_values(
            cur,
            """INSERT INTO votes (id, post_id, vote_type_id, user_id,
               creation_date, bounty_amount)
               VALUES %s ON CONFLICT (id) DO NOTHING""",
            batch
        )
        conn.commit()

    elapsed = time.time() - start_time
    print(f"\n  Done! Imported {count:,} votes in {elapsed:.1f}s")

    cur.close()
    conn.close()
    return count


def import_badges(xml_file: Path):
    """Import badges from XML file."""
    print(f"\n[IMPORT] Importing badges from {xml_file.name}...")

    conn = get_connection()
    cur = conn.cursor()

    batch = []
    count = 0
    start_time = time.time()

    context = ET.iterparse(str(xml_file), events=("end",))

    for event, elem in context:
        if elem.tag == "row":
            row = (
                parse_int(elem.get("Id")),
                parse_int(elem.get("UserId")),
                elem.get("Name"),
                parse_date(elem.get("Date")),
                parse_int(elem.get("Class")),
                parse_bool(elem.get("TagBased")),
            )
            batch.append(row)
            count += 1

            if len(batch) >= BATCH_SIZE:
                execute_values(
                    cur,
                    """INSERT INTO badges (id, user_id, name, date, class, tag_based)
                       VALUES %s ON CONFLICT (id) DO NOTHING""",
                    batch
                )
                conn.commit()
                batch = []
                elapsed = time.time() - start_time
                rate = count / elapsed if elapsed > 0 else 0
                print(f"\r  Imported {count:,} badges ({rate:.0f}/s)...", end="")

            elem.clear()

    if batch:
        execute_values(
            cur,
            """INSERT INTO badges (id, user_id, name, date, class, tag_based)
               VALUES %s ON CONFLICT (id) DO NOTHING""",
            batch
        )
        conn.commit()

    elapsed = time.time() - start_time
    print(f"\n  Done! Imported {count:,} badges in {elapsed:.1f}s")

    cur.close()
    conn.close()
    return count


def import_tags(xml_file: Path):
    """Import tags from XML file."""
    print(f"\n[IMPORT] Importing tags from {xml_file.name}...")

    conn = get_connection()
    cur = conn.cursor()

    batch = []
    count = 0
    start_time = time.time()

    context = ET.iterparse(str(xml_file), events=("end",))

    for event, elem in context:
        if elem.tag == "row":
            row = (
                parse_int(elem.get("Id")),
                elem.get("TagName"),
                parse_int(elem.get("Count")),
                parse_int(elem.get("ExcerptPostId")),
                parse_int(elem.get("WikiPostId")),
            )
            batch.append(row)
            count += 1

            if len(batch) >= BATCH_SIZE:
                execute_values(
                    cur,
                    """INSERT INTO tags (id, tag_name, count, excerpt_post_id, wiki_post_id)
                       VALUES %s ON CONFLICT (id) DO NOTHING""",
                    batch
                )
                conn.commit()
                batch = []

            elem.clear()

    if batch:
        execute_values(
            cur,
            """INSERT INTO tags (id, tag_name, count, excerpt_post_id, wiki_post_id)
               VALUES %s ON CONFLICT (id) DO NOTHING""",
            batch
        )
        conn.commit()

    elapsed = time.time() - start_time
    print(f"\n  Done! Imported {count:,} tags in {elapsed:.1f}s")

    cur.close()
    conn.close()
    return count


def create_indexes():
    """Create indexes for performance."""
    print("\n[INDEX] Creating indexes...")

    conn = get_connection()
    cur = conn.cursor()

    indexes = [
        # Users indexes
        "CREATE INDEX IF NOT EXISTS idx_users_reputation ON users(reputation)",
        "CREATE INDEX IF NOT EXISTS idx_users_creation_date ON users(creation_date)",

        # Posts indexes - these will be analyzed by our agent
        "CREATE INDEX IF NOT EXISTS idx_posts_owner_user_id ON posts(owner_user_id)",
        "CREATE INDEX IF NOT EXISTS idx_posts_creation_date ON posts(creation_date)",
        "CREATE INDEX IF NOT EXISTS idx_posts_post_type_id ON posts(post_type_id)",
        "CREATE INDEX IF NOT EXISTS idx_posts_parent_id ON posts(parent_id)",
        "CREATE INDEX IF NOT EXISTS idx_posts_score ON posts(score)",

        # Comments indexes
        "CREATE INDEX IF NOT EXISTS idx_comments_post_id ON comments(post_id)",
        "CREATE INDEX IF NOT EXISTS idx_comments_user_id ON comments(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_comments_creation_date ON comments(creation_date)",

        # Votes indexes
        "CREATE INDEX IF NOT EXISTS idx_votes_post_id ON votes(post_id)",
        "CREATE INDEX IF NOT EXISTS idx_votes_user_id ON votes(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_votes_vote_type_id ON votes(vote_type_id)",

        # Badges indexes
        "CREATE INDEX IF NOT EXISTS idx_badges_user_id ON badges(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_badges_name ON badges(name)",
    ]

    for idx_sql in indexes:
        idx_name = idx_sql.split("IF NOT EXISTS ")[1].split(" ON")[0]
        print(f"  Creating {idx_name}...")
        cur.execute(idx_sql)
        conn.commit()

    print("[INDEX] Indexes created")

    cur.close()
    conn.close()


def add_foreign_keys():
    """Add foreign key constraints (optional, can slow down imports)."""
    print("\n[FK] Adding foreign key constraints...")

    conn = get_connection()
    cur = conn.cursor()

    # Note: These are commented out by default because they can fail
    # if the data has orphan records (which Stack Exchange data sometimes does)
    fks = [
        # "ALTER TABLE posts ADD CONSTRAINT fk_posts_owner FOREIGN KEY (owner_user_id) REFERENCES users(id)",
        # "ALTER TABLE comments ADD CONSTRAINT fk_comments_post FOREIGN KEY (post_id) REFERENCES posts(id)",
        # "ALTER TABLE comments ADD CONSTRAINT fk_comments_user FOREIGN KEY (user_id) REFERENCES users(id)",
        # "ALTER TABLE votes ADD CONSTRAINT fk_votes_post FOREIGN KEY (post_id) REFERENCES posts(id)",
        # "ALTER TABLE badges ADD CONSTRAINT fk_badges_user FOREIGN KEY (user_id) REFERENCES users(id)",
    ]

    for fk_sql in fks:
        try:
            cur.execute(fk_sql)
            conn.commit()
            print(f"  Added FK: {fk_sql.split('ADD CONSTRAINT ')[1].split(' FOREIGN')[0]}")
        except Exception as e:
            print(f"  Skipped FK (data integrity issue): {e}")
            conn.rollback()

    print("[FK] Foreign keys processed")

    cur.close()
    conn.close()


def analyze_tables():
    """Run ANALYZE on all tables."""
    print("\n[ANALYZE] Updating table statistics...")

    conn = get_connection()
    cur = conn.cursor()

    tables = ["users", "posts", "comments", "votes", "badges", "tags"]

    for table in tables:
        print(f"  Analyzing {table}...")
        cur.execute(f"ANALYZE {table}")
        conn.commit()

    print("[ANALYZE] Statistics updated")

    cur.close()
    conn.close()


def print_summary():
    """Print import summary."""
    print("\n" + "=" * 60)
    print("IMPORT SUMMARY")
    print("=" * 60)

    conn = get_connection()
    cur = conn.cursor()

    tables = ["users", "posts", "comments", "votes", "badges", "tags"]

    for table in tables:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]

        cur.execute(f"""
            SELECT pg_size_pretty(pg_total_relation_size('{table}'))
        """)
        size = cur.fetchone()[0]

        print(f"  {table:12}: {count:>15,} rows ({size})")

    cur.execute("SELECT pg_size_pretty(pg_database_size(current_database()))")
    total_size = cur.fetchone()[0]
    print(f"\n  Total database size: {total_size}")

    cur.close()
    conn.close()


def main():
    """Main import function."""
    print("=" * 60)
    print("Stack Exchange PostgreSQL Importer")
    print("=" * 60)

    # Find XML files
    xml_files = list(DATA_DIR.glob("*.xml"))

    if not xml_files:
        print(f"\n[ERROR] No XML files found in {DATA_DIR}")
        print("Run download_stackexchange.py first to download the data.")
        sys.exit(1)

    print(f"\n[INFO] Found {len(xml_files)} XML file(s):")
    for f in xml_files:
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name}: {size_mb:.1f} MB")

    # Create database and schema
    create_database()
    create_schema()

    # Import each file type
    file_handlers = {
        "Users.xml": import_users,
        "Posts.xml": import_posts,
        "Comments.xml": import_comments,
        "Votes.xml": import_votes,
        "Badges.xml": import_badges,
        "Tags.xml": import_tags,
    }

    for xml_file in xml_files:
        for pattern, handler in file_handlers.items():
            if xml_file.name.endswith(pattern):
                handler(xml_file)
                break

    # Create indexes
    create_indexes()

    # Add foreign keys (optional)
    # add_foreign_keys()

    # Update statistics
    analyze_tables()

    # Print summary
    print_summary()

    print("\n[DONE] Import complete!")
    print("\n[NEXT] You can now run the backend API:")
    print("       cd backend && source venv/bin/activate && python main.py")


if __name__ == "__main__":
    main()
