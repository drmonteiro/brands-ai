import asyncio
import sys
import os

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.services.vector_db import populate_clients_database

if __name__ == "__main__":
    print("Refreshing ChromaDB from lanca_clients.py...")
    asyncio.run(populate_clients_database(force_refresh=True))
    print("Done.")
