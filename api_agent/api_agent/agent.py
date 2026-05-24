import json
import re
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
from openai import AsyncOpenAI
import database as db
import math_mcp
import aiosqlite
import math_mcp

async def run_agent_loop(chat_id: str, user_id: str):

    llm_config = await db.get_llm_config(user_id)

    if not llm_config:
        return "Error you do not have llm config"

    api_key = llm_config["api_key"]
    if not api_key or str(api_key).strip() == "":
        api_key = "dummy_key_to_force_header"

    client = AsyncOpenAI(
        api_key=api_key,
        base_url=llm_config["base_url"],
        default_headers={
            "Authorization": f"Bearer {llm_config['api_key']}",
            "HTTP-Referer": "http://localhost",
            "X-Title": "My Agent"
        }
    )
    model_name = llm_config["model"]
    raw_history = await db.get_chat_history(chat_id)

    messages = [{"role": "system", "content": "You are ai agent, use special tools if there are available ones."}]
    for msg in raw_history:
        messages.append({"role": msg["role"], "content": msg["text"]})

    available_tools = await get_tools_from_mcps(chat_id, user_id)

    iterations = 0
    consecutive_tool_calls = 0
    last_tool_name = None
    used_tools = []

    while iterations < 10:
        iterations += 1
        # test func for success connection 
        print(f"Sending tools: {available_tools}")


        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=messages,
                tools=available_tools if available_tools else None,
                temperature=0.7
            )
        except Exception as e:
            error_msg = f"LLM API Error: {str(e)}"
            await db.save_message(chat_id, "assistant", error_msg)
            return error_msg

        ai_message = response.choices[0].message
        
        assistant_msg = {
            "role": "assistant",
            "content": ai_message.content
        }

        if ai_message.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                }
                for tc in ai_message.tool_calls
            ]
            
        messages.append(assistant_msg)
        
        if ai_message.tool_calls:
            for tool_call in ai_message.tool_calls:
                tool_name = tool_call.function.name
                used_tools.append(tool_name)
                try:
                    tool_args = json.loads(tool_call.function.arguments)
                    if not isinstance(tool_args, dict):
                        tool_args = {}
                except Exception:
                    tool_args = {}

                if tool_name == last_tool_name:
                    consecutive_tool_calls += 1
                else:
                    consecutive_tool_calls = 1
                    last_tool_name = tool_name

                if consecutive_tool_calls > 2:
                    error_msg = f"Error: we are in cycle: {tool_name}."
                    await db.save_message(chat_id, "assistant", error_msg)
                    return error_msg

                print(f"Using tool: {tool_name}")
                tool_result = await execute_mcp_tool(chat_id, user_id, tool_name, tool_args)

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "name": tool_name,
                    "content": str(tool_result)
                })
            
            continue 

        else:
            content_text = ai_message.content
            
            # This code i made to parse jsons, cause AI respond me just json. Don't fight if it's illegal pls
            if content_text and '"name"' in content_text and '"arguments"' in content_text:
                try:
                    match = re.search(r'\{.*\}', content_text, re.DOTALL)
                    if match:
                        tool_data = json.loads(match.group(0))
                        tool_name = tool_data.get("action") or tool_data.get("name")
    
                        raw_args = tool_data.get("action_input", {})
                        used_tools.append(str(tool_name))
                        tool_args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args

                        tool_result = await execute_mcp_tool(chat_id, user_id, tool_name, tool_args)
                        
                        messages.append({
                            "role": "user",
                            "content": f"System observation: The tool '{tool_name}' was called and returned the result: {tool_result}. Based on this result, provide the final answer to the user."
                        })
                        

                        continue 
                        
                except Exception as e:
                    print(f"Error while parsing: {e}")
            
            content_text = content_text or ""
            final_answer = content_text

            if used_tools:
                final_answer += f"\n\n[System note: Tools used: {', '.join(used_tools)}]"

            await db.save_message(chat_id, "assistant", final_answer)
            return final_answer


    error_msg = "Eror: out of iteration limit."
    await db.save_message(chat_id, "assistant", error_msg)
    return error_msg


async def _get_mcp_configs(chat_id: str, user_id: str):
    """
    Private func to get all mcp configs connected to chat
    """
    configs = []
    async with aiosqlite.connect(db.DB_PATH) as conn:
        async with conn.execute("SELECT mcp_ids FROM chats WHERE chat_id = ? AND user_id = ?", (chat_id, user_id)) as cursor:
            row = await cursor.fetchone()
            if not row: return []
            mcp_ids = json.loads(row[0])
        if not mcp_ids: return []

        placeholders = ",".join("?" * len(mcp_ids))
        query = f"SELECT id, name, url, token FROM mcp_configs WHERE id IN ({placeholders}) AND user_id = ?"
        async with conn.execute(query, tuple(mcp_ids) + (user_id, )) as cursor:
            rows = await cursor.fetchall()
            for r in rows:
                configs.append({"id": r[0], "name": r[1], "url": r[2], "token": r[3]})
    return configs


async def get_tools_from_mcps(chat_id: str, user_id: str):
    """
    Going through all connected MCP servers and 
    making list of available tools in OpenAI format
    """
    list_of_tools = [
        {
            "type": "function",
            "function": {
                "name": "internal_multiply_by_two",
                "description": "Multiply given number by 2",
                "parameters": {
                    "type": "object",
                    "properties": {"number": {"type": "number"}},
                    "required": ["number"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "internal_divide",
                "description": "Divide a by b",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "a": {"type": "number"},
                        "b": {"type": "number"}
                    },
                    "required": ["a", "b"]
                }
            }
        }
    ]

    mcp_configs = await _get_mcp_configs(chat_id, user_id)
    for config in mcp_configs:
        headers = {"Authorization": f"Bearer {config['token']}"} if config['token'] else {}
        url = config['url']
        if not url.endswith('/sse'):
            url = url.rstrip('/') + '/sse'
        try:
            async with sse_client(url=config['url'], headers=headers) as streams:
                async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()

                    result = await session.list_tools()
                    for tool in result.tools:
                        list_of_tools.append({
                            "type": "function",
                            "function": {
                                "name": f"mcp{config['id']}_{tool.name}",
                                "description": tool.description or "",
                                "parameters": tool.inputSchema
                            }
                        })
        except Exception as exp:
            print(f"Error connecting to MCP: {exp}")
    return list_of_tools


async def execute_mcp_tool(chat_id, user_id, tool_name: str, args: dict):
    """
    Execute mcp tool
    """
    if tool_name == "internal_multiply_by_two":
        return str(math_mcp.multiply_by_two(args.get("number", 0)))
    
    if tool_name == "internal_divide":
        return str(math_mcp.divide(args.get("a", 0), args.get("b", 1)))

    try:
        mcp_id_str, real_tool_name = tool_name.split("_", 1)
        mcp_id = int(mcp_id_str.replace("mcp", ""))
    except ValueError:
        return "Oops you have wrong tool name"
    
    mcp_configs = await _get_mcp_configs(chat_id, user_id)
    target_config = next((c for c in mcp_configs if c["id"] == mcp_id), None)
    
    if not target_config:
        return "Your mcp server is disconnected or not found"
    
    headers = {"Authorization": f"Bearer {target_config['token']}"} if target_config['token'] else {}
    
    url = target_config['url']
    if not url.endswith('/sse'):
        url = url.rstrip('/') + '/sse'

    try:
        async with sse_client(url=url, headers=headers) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                    await session.initialize()
                    result = await session.call_tool(real_tool_name, arguments=args)
                    if result.content and len(result.content) > 0:
                        return result.content[0].text
                    return "Here is no text returned from server"
    except Exception as exp:
        return f"Oops mistake. here is the code:{exp}"
