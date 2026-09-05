import asyncio
import os
import asyncpg
from dotenv import load_dotenv

load_dotenv()

raw_url = os.environ.get("NEON_DATABASE_URL", "")
# Clean up URL for asyncpg: strip unsupported query parameters like channel_binding
clean_url = raw_url.split("?")[0]

async def inspect():
    print(f"Connecting to: {clean_url[:40]}...")
    conn = await asyncpg.connect(clean_url, ssl="require")
    
    # 1. Current DB and user
    db = await conn.fetchval("SELECT current_database()")
    user = await conn.fetchval("SELECT current_user")
    print(f"Connected to database: {db} as {user}")
    
    # 2. List all databases on this cluster
    dbs = await conn.fetch("SELECT datname FROM pg_database WHERE datistemplate = false;")
    print("Databases on cluster:", [d["datname"] for d in dbs])
    
    # 3. List all schemas
    schemas = await conn.fetch("SELECT schema_name FROM information_schema.schemata WHERE schema_name NOT IN ('pg_catalog', 'information_schema')")
    print("Schemas:", [s["schema_name"] for s in schemas])
    
    # 4. Check all tables and row counts in each schema
    tables = await conn.fetch("""
        SELECT table_schema, table_name 
        FROM information_schema.tables 
        WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
        ORDER BY table_schema, table_name;
    """)
    print(f"\nFound {len(tables)} tables/views:")
    for t in tables:
        s, tbl = t["table_schema"], t["table_name"]
        try:
            cnt = await conn.fetchval(f'SELECT COUNT(*) FROM "{s}"."{tbl}"')
            if cnt > 0:
                print(f"  >>> {s}.{tbl}: {cnt} rows")
            else:
                print(f"      {s}.{tbl}: 0 rows")
        except Exception as e:
            print(f"      {s}.{tbl}: error reading ({e})")
            
    await conn.close()

if __name__ == "__main__":
    asyncio.run(inspect())
