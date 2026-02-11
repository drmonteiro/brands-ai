import chromadb
import os

# Define ChromaDB path
CHROMA_PATH = os.path.join(os.path.dirname(__file__), "chroma_db")

def inspect_chromadb():
    if not os.path.exists(CHROMA_PATH):
        print(f"ChromaDB not found at {CHROMA_PATH}")
        return

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collections = client.list_collections()
    
    print(f"Found {len(collections)} collections in ChromaDB:")
    
    for col in collections:
        print(f"\nCollection: {col.name}")
        collection = client.get_collection(col.name)
        count = collection.count()
        print(f"  - Count: {count}")
        
        if count > 0:
            # Check a sample for metadata keys
            results = collection.peek(limit=5)
            metadatas = results['metadatas']
            print("  - Sample Metadata Keys:", list(metadatas[0].keys()) if metadatas else "None")
            
            # Check specifically for London/Boston in metadata
            print("  - Checking for 'London' or 'Boston' in metadata...")
            london_results = collection.get(where={"city": "London"})
            boston_results = collection.get(where={"city": "Boston"})
            
            print(f"    - Found {len(london_results['ids'])} entries for London")
            print(f"    - Found {len(boston_results['ids'])} entries for Boston")

if __name__ == "__main__":
    inspect_chromadb()
