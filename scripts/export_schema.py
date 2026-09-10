"""Export JSON Schemas directly from the Pydantic contracts."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tender_basic.models import ProjectFacts, ResolutionOverrides  # noqa: E402


def main() -> int:
    output_dir = ROOT / "schemas"
    output_dir.mkdir(parents=True, exist_ok=True)
    schemas = {
        "project_facts.schema.json": ProjectFacts,
        "resolution_overrides.schema.json": ResolutionOverrides,
    }
    for filename, model in schemas.items():
        output_path = output_dir / filename
        output_path.write_text(
            json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(output_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
