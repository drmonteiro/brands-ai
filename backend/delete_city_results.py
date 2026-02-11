import sqlite3
import os
import sys

# Define database path
DB_PATH = os.path.join(os.path.dirname(__file__), "prospects.sqlite")

def delete_cities(cities):
    """
    Delete all prospects and search records for the specified cities.
    """
    if not os.path.exists(DB_PATH):
        print(f"Error: Database not found at {DB_PATH}")
        return

    print(f"Connecting to database at: {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        for city in cities:
            normalized_city = city.lower().strip()
            print(f"\nProcessing city: {city} (normalized: {normalized_city})")

            # 1. Count prospects to be deleted
            cursor.execute("SELECT COUNT(*) FROM prospects WHERE searched_city = ?", (normalized_city,))
            count = cursor.fetchone()[0]
            
            if count > 0:
                # 2. Delete from prospects table
                cursor.execute("DELETE FROM prospects WHERE searched_city = ?", (normalized_city,))
                print(f"  - Deleted {count} prospects from 'prospects' table.")
            else:
                print(f"  - No prospects found in 'prospects' table.")

            # 3. Check searched_cities table
            cursor.execute("SELECT COUNT(*) FROM searched_cities WHERE normalized_city = ?", (normalized_city,))
            city_count = cursor.fetchone()[0]

            if city_count > 0:
                # 4. Delete from searched_cities table
                cursor.execute("DELETE FROM searched_cities WHERE normalized_city = ?", (normalized_city,))
                print(f"  - Deleted record from 'searched_cities' table.")
            else:
                print(f"  - No record found in 'searched_cities' table.")

        conn.commit()
        print("\n✅ Deletion completed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Error during deletion: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # Cities to delete
    cities_to_delete = ["london", "boston"]
    
    # Allow command line arguments
    if len(sys.argv) > 1:
        cities_to_delete = sys.argv[1:]
        
    delete_cities(cities_to_delete)
