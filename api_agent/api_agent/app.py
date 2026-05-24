import os
import uuid
import json
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(current_dir)

import aiosqlite
import agent
from fastapi import FastAPI, Header, Depends, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import database as db

load_dotenv()

main = FastAPI(
    title="Simple Agent API",
    description="""
    **Authentication Documentation:**
    All protected endpoints require authentication via headers.
    You must provide:
    - `x-auth-token`: The secret authorization token.
    - `x-user-id`: The identifier of the user for data isolation.
    """
)

# secret token for default access and testing
SECRET_TOKEN = os.getenv("SECRET_AUTH_TOKEN", "default-secret")

async def get_current_user(
    x_auth_token: str = Header(..., alias="x-auth-token", description="Security mechanism: Authentication token"), 
    x_user_id: str = Header(..., alias="x-user-id", description="Security mechanism: User ID")
):
    """
    func for token check
    """
    if x_auth_token != SECRET_TOKEN:
        raise HTTPException(status_code=401, detail="Wrong authorization token")
    return x_user_id


class LLMConfigCreate(BaseModel):
    base_url: str = Field(..., description="URL for connecting via API")
    api_key: str = Field(..., description="Access token for LLM")
    model: str = Field(..., description="LLM model name")


class MCPConfigCreate(BaseModel):
    name: str = Field(..., description="MCP server's name")
    url: str = Field(..., description="URL Streamable HTTP MCP")
    token: str = Field(..., description="Authorization token")


class MessageCreate(BaseModel):
    text: str = Field(..., description="User message text")


class MessageResponse(BaseModel):
    answer: str


class AttachMCPRequest(BaseModel):
    mcp_id: int = Field(..., description="MCP server's id which should be connected to chat")


@main.on_event("startup")
async def startup_event():
    await db.init_db()


@main.post("/llm-configs")
async def add_llm_config(config: LLMConfigCreate, user_id: str = Depends(get_current_user)):
    await db.save_llm_config(user_id, config.base_url, config.api_key, config.model)
    return {"status": "success", "message": "LLM config is saved"}

@main.get("/llm-configs")
async def get_llm_configs(user_id: str = Depends(get_current_user)):
    config = await db.get_llm_config(user_id)
    if config:
        config["user_id"] = user_id
        return [config]
    return [config] if config else []


@main.post("/mcp-configs")
async def add_mcp_config(config: MCPConfigCreate, user_id: str = Depends(get_current_user)):
    await db.save_mcp_config(user_id, config.name, config.url, config.token)
    return {"status": "success", "message": "MCP config is added"}


@main.get("/mcp-configs")
async def list_mcp_configs(user_id: str = Depends(get_current_user)):
    """Посмотреть все свои MCP-конфиги и их ID"""
    configs = await db.get_mcp_configs(user_id)
    return {"configs": configs}


@main.post("/chats")
async def create_new_chat(user_id: str = Depends(get_current_user)):
    # chat ID generation
    chat_id = uuid.uuid4().hex
    await db.create_chat(chat_id, user_id)
    return {"chat_id": chat_id}


@main.get("/chats/{chat_id}")
async def get_chat(chat_id: str, user_id: str = Depends(get_current_user)):
    async with aiosqlite.connect(db.DB_PATH) as conn:
        async with conn.execute( "SELECT user_id FROM chats WHERE chat_id = ?", (chat_id,)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Chat not found")
            if row[0] != user_id:
                raise HTTPException(status_code=403, detail="Access denied to this chat")

    history = await db.get_chat_history(chat_id)
    return {"chat_id": chat_id, "history": history}


@main.post("/chats/{chat_id}/mcp")
async def attach_mcp_to_chat(chat_id: str, request: AttachMCPRequest, user_id: str = Depends(get_current_user)):
    async with aiosqlite.connect(db.DB_PATH) as conn:
        async with conn.execute("SELECT mcp_ids FROM chats WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Chat is not found")
            
            mcp_list = json.loads(row[0])
            if request.mcp_id not in mcp_list:
                mcp_list.append(request.mcp_id)
                await db.update_chat_mcps(chat_id, mcp_list)
                
    return {"status": "success", "mcp_ids": mcp_list}


@main.delete("/chats/{chat_id}/mcp/{mcp_id}")
async def detach_mcp_from_chat(chat_id: str, mcp_id: int, user_id: str = Depends(get_current_user)):
    async with aiosqlite.connect(db.DB_PATH) as conn:
        async with conn.execute("SELECT mcp_ids FROM chats WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Chat not found")
            
            mcp_list = json.loads(row[0])
            if mcp_id in mcp_list:
                mcp_list.remove(mcp_id)
                await db.update_chat_mcps(chat_id, mcp_list)
                
    return {"status": "success", "mcp_ids": mcp_list}


@main.post("/chats/{chat_id}/messages")
async def send_message(chat_id: str, message: MessageCreate, user_id: str = Depends(get_current_user)):

    await db.save_message(chat_id, "user", message.text)

    ai_response_text = await agent.run_agent_loop(chat_id, user_id)
    
    return {"response": ai_response_text}
