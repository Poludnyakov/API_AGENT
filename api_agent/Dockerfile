FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .

RUN pip install --no-cache-dir fastapi uvicorn aiosqlite openai mcp fastmcp python-dotenv

COPY . .

WORKDIR /app/api_agent

EXPOSE 40142

CMD ["uvicorn", "app:main", "--host", "0.0.0.0", "--port", "40142"]
