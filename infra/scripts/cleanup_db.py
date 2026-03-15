"""
Script to clear all data from Firestore collections for a fresh start.
Collections: workflows, businesses, adk_sessions, zipcode_research, area_research, sector_research, heartbeats, discovery_jobs, agent_results.
"""

import asyncio
import os
from google.cloud import firestore
from dotenv import load_dotenv

# Load env for PROJECT_ID
load_dotenv()

PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "hephae-co-dev")

COLLECTIONS = [
    "workflows",
    "businesses",
    "adk_sessions",
    "zipcode_research",
    "area_research",
    "sector_research",
    "heartbeats",
    "discovery_jobs",
    "agent_results"
]

async def delete_collection(db, col_name, batch_size=500):
    """Delete all documents in a collection in batches."""
    col_ref = db.collection(col_name)
    deleted_total = 0
    
    while True:
        docs = await asyncio.to_thread(lambda: list(col_ref.limit(batch_size).stream()))
        if not docs:
            break
            
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
            
        await asyncio.to_thread(batch.commit)
        deleted_total += len(docs)
        print(f"  Deleted {len(docs)} documents from '{col_name}'...")
        
    return deleted_total

async def main():
    print(f"🚀 Starting database cleanup for project: {PROJECT_ID}")
    
    # Initialize Firestore client
    db = firestore.Client(project=PROJECT_ID)
    
    for col in COLLECTIONS:
        print(f"🧹 Clearing collection: {col}")
        try:
            count = await delete_collection(db, col)
            print(f"✅ Successfully cleared '{col}' ({count} docs deleted).")
        except Exception as e:
            print(f"❌ Error clearing '{col}': {e}")
            
    print("\n✨ Database cleanup complete. Everything is fresh!")

if __name__ == "__main__":
    confirm = input(f"WARNING: This will delete ALL data in {COLLECTIONS} for project {PROJECT_ID}. Type 'DELETE' to confirm: ")
    if confirm == "DELETE":
        asyncio.run(main())
    else:
        print("❌ Cleanup cancelled.")
