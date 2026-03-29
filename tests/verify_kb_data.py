"""
Verify KB data was saved correctly to the database.
Check that detail fields are not NULL and contain proper JSON.
"""

import os
from sqlalchemy import create_engine, text
import json

db_url = "postgresql://user:password@localhost:5433/bizclone"
engine = create_engine(db_url, echo=False)

def verify_kb_data():
    with engine.connect() as conn:
        # Get the latest KB entries
        result = conn.execute(text("""
            SELECT version_id, kb_field, item_key, detail, change_description, is_active
            FROM knowledge_base
            WHERE is_active = TRUE
            ORDER BY version_id DESC
            LIMIT 10
        """))
        
        print("=" * 100)
        print("LATEST ACTIVE KB ENTRIES (Top 10)")
        print("=" * 100)
        
        for row in result:
            version_id, kb_field, item_key, detail, change_desc, is_active = row
            print(f"\nVersion: {version_id}")
            print(f"Field:   {kb_field}")
            print(f"Item:    {item_key}")
            print(f"Active:  {is_active}")
            print(f"Change:  {change_desc}")
            print(f"Detail Type: {type(detail).__name__}")
            
            # Check if detail is NULL
            if detail is None:
                print(f"WARNING: detail is NULL!")
            else:
                # If it's a dict, print it nicely
                if isinstance(detail, dict):
                    print(f"Detail (dict): {json.dumps(detail, indent=2)[:100]}...")
                else:
                    print(f"Detail: {str(detail)[:100]}...")

def check_problematic_entries():
    """Check if there are any entries with NULL detail"""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT COUNT(*) as null_count
            FROM knowledge_base
            WHERE detail IS NULL
        """))
        
        null_count = result.scalar()
        print(f"\n\n{'='*100}")
        print(f"ENTRIES WITH NULL DETAIL: {null_count}")
        print(f"{'='*100}")
        
        if null_count > 0:
            print("WARNING: Found entries with NULL detail!")
            result2 = conn.execute(text("""
                SELECT version_id, kb_field, item_key, change_description
                FROM knowledge_base
                WHERE detail IS NULL
                LIMIT 5
            """))
            print("\nFirst 5 entries with NULL detail:")
            for row in result2:
                print(f"  Version {row[0]}: {row[1]}[{row[2]}] - {row[3]}")
        else:
            print("✓ Good: No entries with NULL detail!")

if __name__ == "__main__":
    verify_kb_data()
    check_problematic_entries()
