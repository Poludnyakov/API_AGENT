import aiosqlite
import json

DB_PATH = "ai_agent.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
#llm configs table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS llm_configs (
                user_id TEXT PRIMARY KEY,
                base_url TEXT,
                api_key TEXT,
                model TEXT
            )
        """)
# mcp configs table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS mcp_configs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT,
                name TEXT,
                url TEXT,
                token TEXT
            )
        """)
# chat table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id TEXT PRIMARY KEY,
                user_id TEXT,
                mcp_ids TEXT  -- Храним как JSON-строку список ID
            )
        """)
# message table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT,
                role TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await db.commit()


async def save_llm_config(user_id, base_url, api_key, model):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT OR REPLACE INTO llm_configs (user_id, base_url, api_key, model)
            VALUES (?, ?, ?, ?)
        """, (user_id, base_url, api_key, model))
        await db.commit()

async def get_llm_config(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT base_url, api_key, model FROM llm_configs WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return {"base_url": row[0], "api_key": row[1], "model": row[2]}
            return None

async def save_message(chat_id, role, content):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)", 
                         (chat_id, role, content))
        await db.commit()

async def get_chat_history(chat_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT role, content FROM messages WHERE chat_id = ? ORDER BY timestamp", (chat_id,)) as cursor:
            rows = await cursor.fetchall()
            return [{"role": r, "text": c} for r, c in rows]

async def save_mcp_config(user_id, name, url, token):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO mcp_configs (user_id, name, url, token)
            VALUES (?, ?, ?, ?)
        """, (user_id, name, url, token))
        await db.commit()

async def get_mcp_configs(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, url, token FROM mcp_configs WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [{"id": r[0], "name": r[1], "url": r[2], "token": r[3]} for r in rows]

async def create_chat(chat_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR IGNORE INTO chats (chat_id, user_id, mcp_ids) VALUES (?, ?, ?)", 
                         (chat_id, user_id, "[]"))
        await db.commit()

async def update_chat_mcps(chat_id, mcp_ids_list):
    mcp_ids_json = json.dumps(mcp_ids_list) 
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE chats SET mcp_ids = ? WHERE chat_id = ?", (mcp_ids_json, chat_id))
        await db.commit()
