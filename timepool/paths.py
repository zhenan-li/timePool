import os
import sys
from pathlib import Path


def user_data_root() -> Path:
    if getattr(sys, "frozen", False):
        local = Path(os.environ["LOCALAPPDATA"]) if os.environ.get("LOCALAPPDATA") else Path.home()
        return local / "Time Pool"
    return Path(__file__).resolve().parent.parent
