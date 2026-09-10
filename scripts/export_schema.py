"""Export the JSON Schema directly from the Pydantic ProjectFacts model."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tender_basic.models import ProjectFacts  # noqa: E402


def main() -> int:
    output_path = ROOT / "schemas" / "project_facts.schema.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    schema = ProjectFacts.model_json_schema()
    output_path.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
