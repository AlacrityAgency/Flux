"""Configuration settings for Flux Agentic Engine."""

import os
import sys
from pathlib import Path
from pydantic import BaseModel, Field


class Settings(BaseModel):
    gapgpt_base_url: str = Field(default="https://api.gapgpt.app/v1")
    enable_live: bool = Field(default=False)
    default_provider: str = Field(default="fake")  # "fake" or "gapgpt"
    db_path: str = Field(default="var/flux.db")

    # Hard execution constraints
    max_subtasks: int = 5
    max_subtask_attempts: int = 3
    max_concurrent_agents: int = 2
    max_root_calls: int = 20
    max_fable_calls: int = 2
    max_active_runtime_seconds: int = 20 * 60  # 20 minutes
    max_network_retries: int = 2

    @property
    def gapgpt_api_key(self) -> str:
        """Read API key exclusively from environment variable."""
        return os.environ.get("GAPGPT_API_KEY", "")


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
    api_key = os.environ.get("GAPGPT_API_KEY", "").strip()
    enable_live_raw = os.environ.get("FLUX_ENABLE_LIVE", "1" if api_key else "0")
    enable_live_env = enable_live_raw.lower() in ("1", "true", "yes") and bool(api_key)
    default_prov = "gapgpt" if enable_live_env else "fake"
    default_db = str(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "FluxDemo" / "flux.db") if getattr(sys, "frozen", False) else "var/flux.db"
    base_url = os.environ.get("GAPGPT_BASE_URL", "https://api.gapgpt.app/v1")
    return Settings(
        gapgpt_base_url=base_url,
        enable_live=enable_live_env,
        default_provider=default_prov,
        db_path=os.environ.get("FLUX_DB_PATH", default_db)
    )
