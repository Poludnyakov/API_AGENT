import json
from pathlib import Path

from api_agent.app import main


def generate() -> None:
    output_path = Path(__file__).with_name("swagger.json")
    output_path.write_text(
        json.dumps(main.openapi(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(output_path)


if __name__ == "__main__":
    generate()
