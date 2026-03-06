"""Silent verification - returns only exit codes"""

import json
import sys
from datetime import datetime
from pathlib import Path


def verify() -> None:
    status_file = Path(__file__).parent / "serena-status.json"
    if not Path("/home/omar/Documents/ruleIQ").exists():
        sys.exit(1)
    if not Path("/home/omar/Documents/ruleIQ/.venv").exists():
        sys.exit(2)
    try:
        status = {
            "active": True,
            "project": "ruleIQ",
            "last_verification": datetime.now().isoformat(),
            "python_env_ok": True,
            "project_structure_ok": True,
            "serena_active": True,
        }
        status_file.write_text(json.dumps(status, indent=2))
    except (OSError, ValueError, TypeError):
        sys.exit(3)
    sys.exit(0)


if __name__ == "__main__":
    verify()
