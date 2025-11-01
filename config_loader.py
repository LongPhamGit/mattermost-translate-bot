import os
import json
from pathlib import Path


CONFIG_ENV_VAR = "MATTERMOST_TRANSLATE_CONFIG"
_module_dir = Path(__file__).resolve().parent


def _resolve_config_path() -> Path:
    """Locate the configuration file with a few sensible fallbacks."""

    candidates = []

    env_path = os.environ.get(CONFIG_ENV_VAR)
    if env_path:
        candidates.append(Path(env_path).expanduser())

    candidates.append(Path.cwd() / "config.json")
    candidates.append(_module_dir / "config.json")

    for path in candidates:
        if path and path.exists():
            return path

    searched = ", ".join(str(p) for p in candidates if p)
    raise SystemExit(
        f"Missing config.json. Set {CONFIG_ENV_VAR} to the config file location. "
        f"Searched: {searched}"
    )


CONFIG_FILE = _resolve_config_path()

with CONFIG_FILE.open("r", encoding="utf-8") as f:
    config = json.load(f)

SERVER_URL      = config.get("SERVER_URL", "http://localhost:8065")
WS_URL          = config.get("WS_URL", "ws://localhost:8065/api/v4/websocket")
MMUSERID        = config.get("MMUSERID", "")
MMAUTHTOKEN     = config.get("MMAUTHTOKEN", "")
MY_USERNAME     = config.get("MY_USERNAME", "lpham")
WATCH_CHANNELS  = config.get("WATCH_CHANNELS", [])
CHANNEL_MAP     = config.get("_comment", {})
USER_MAP        = config.get("USER_MAP", {})
API_KEY         = config.get("API_KEY", "")
GEMINI_URL      = config.get("GEMINI_URL", "")
HTML_LOG_FILE   = config.get("HTML_LOG", "messages.html")

cookies = {"MMUSERID": MMUSERID, "MMAUTHTOKEN": MMAUTHTOKEN}
