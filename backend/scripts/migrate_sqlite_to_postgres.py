import sqlite3
import psycopg2
import os
import json
from dotenv import load_dotenv

load_dotenv()

SQLITE_PATH = os.path.join(os.path.dirname(__file__), "..", "prospects.sqlite")
PG_URL = os.getenv("SYNC_DATABASE_URL")

def migrate():
    if not os.path.exists(SQLITE_PATH):
        print(f"❌ SQLite database not found at {SQLITE_PATH}")
        return

    print(f"🔄 Migrating data from {SQLITE_PATH} to PostgreSQL...")

    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_curr = sqlite_conn.cursor()

    try:
        pg_conn = psycopg2.connect(PG_URL)
        pg_curr = pg_conn.cursor()
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        print("💡 Make sure Docker container is running: 'docker-compose up -d'")
        return

    # 1. Migrate Prospects
    sqlite_curr.execute("SELECT * FROM prospects")
    rows = sqlite_curr.fetchall()
    
    migrated_count = 0
    for row in rows:
        data = dict(row)
        
        # Parse store count (might be string in older versions)
        try:
            store_count = int(data.get('store_count', 0))
        except:
            store_count = 0

        # Handle JSON fields (if any in SQLite)
        material_composition = data.get('material_composition')
        if material_composition and isinstance(material_composition, str):
            try:
                material_composition = json.loads(material_composition)
            except:
                material_composition = []
        
        sustainability_certs = data.get('sustainability_certs')
        if sustainability_certs and isinstance(sustainability_certs, str):
            try:
                sustainability_certs = json.loads(sustainability_certs)
            except:
                sustainability_certs = []

        try:
            pg_curr.execute("""
                INSERT INTO prospects (
                    id, name, website_url, domain, city, country, country_code,
                    store_count, avg_suit_price_eur, brand_style, company_overview,
                    material_composition, sustainability_certs, made_to_measure,
                    heritage_brand, quality_score, similarity_score, location_score,
                    final_score, status, notes, discovered_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET
                    name = EXCLUDED.name,
                    website_url = EXCLUDED.website_url,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                data.get('id'), data.get('name'), data.get('website_url'), data.get('domain'),
                data.get('city'), data.get('country'), data.get('country_code'),
                store_count, data.get('avg_suit_price_eur'), data.get('brand_style'),
                data.get('company_overview'), json.dumps(material_composition), 
                json.dumps(sustainability_certs), data.get('made_to_measure', False),
                data.get('heritage_brand', False), data.get('quality_score', 0),
                data.get('similarity_score', 0), data.get('location_score', 0),
                data.get('final_score', 0), data.get('status', 'new'),
                data.get('notes'), data.get('discovered_at')
            ))
            migrated_count += 1
        except Exception as e:
            print(f"⚠️ Failed to migrate prospect {data.get('name')}: {e}")
            pg_conn.rollback()
            continue

    pg_conn.commit()
    print(f"✅ Migrated {migrated_count} prospects.")

    # 2. Migrate Email Logs (if exists)
    try:
        sqlite_curr.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_logs'")
        if sqlite_curr.fetchone():
            sqlite_curr.execute("SELECT * FROM email_logs")
            logs = sqlite_curr.fetchall()
            log_count = 0
            for log in logs:
                d = dict(log)
                pg_curr.execute("""
                    INSERT INTO email_logs (brand_name, website_url, status, error_message, sent_at)
                    VALUES (%s, %s, %s, %s, %s)
                """, (d.get('brand_name'), d.get('website_url'), d.get('status'), d.get('error_message'), d.get('sent_at')))
                log_count += 1
            pg_conn.commit()
            print(f"✅ Migrated {log_count} email logs.")
    except Exception as e:
        print(f"⚠️ email_logs migration skipped: {e}")

    sqlite_conn.close()
    pg_conn.close()
    print("🏁 Migration complete.")

if __name__ == "__main__":
    migrate()
