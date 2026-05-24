Here is the simple AI agent

base URL http://ai360.velkerr.ru:40142
URL for testing: http://ai360.velkerr.ru:40142/docs

Some things you should know about:
local launch
SECRET_AUTH_TOKEN: If you do not have .env file just use default value
Also you can write your own

launch in Docker:
SECRET_AUTH_TOKEN: it will be send through MR


About x-user-id - just make simple name and enter the same every time you work on one chat. 
All data (chats, configurations, history) is strictly isolated per user. To maintain your context and access your specific chats, please use the exact same x-user-id across your requests

chat-id: it will be shown to you after calling method "create chat". 
Copy it and paste in every other request 
if you want to be in the same chat and context

I'v done my best on this task, so contact me please if something is broken or wrong 

tg: @vovapoludnyakov

Note: The SQLite database (ai_agent.db) is mounted as a Docker volume. All your chats, LLM configs, and MCP configs are saved safely and will persist even if the container restarts.

Built-in Tools The mathematical tools (multiply_by_two, divide) are built-in and available by default as per the task requirements. You can test them immediately by asking the agent to calculate something, without the need to manually register an external MCP server.
