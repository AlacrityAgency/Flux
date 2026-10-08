"""Configuration settings for Flux Agentic Engine."""

import os
import sys
from pathlib import Path
from pydantic import BaseModel, Field


class Settings(BaseModel):
    default_provider: str = Field(default="fake")  # no paid API provider is connected
    db_path: str = Field(default="var/flux.db")

    # Hard execution constraints
    max_subtasks: int = 5
    max_subtask_attempts: int = 3
    max_concurrent_agents: int = 2
    max_root_calls: int = 20
    max_fable_calls: int = 2
    max_active_runtime_seconds: int = 20 * 60  # 20 minutes
    max_network_retries: int = 2


def load_env_files():
    """Load environment variables from candidate .env files if not already in os.environ."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parent.parent.parent / ".env",
        Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / "Flux" / ".env",
        Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FluxDemo" / ".env",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_file():
            try:
                for line in candidate.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip("'\"")
                        if k and k not in os.environ:
                            os.environ[k] = v
            except Exception:
                pass


def get_settings() -> Settings:
    load_env_files()
    default_db = str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FluxDemo" / "flux.db") if getattr(sys, "frozen", False) else "var/flux.db"
    return Settings(
        db_path=os.environ.get("FLUX_DB_PATH", default_db)
    )
