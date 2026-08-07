import os
import tomllib
from pathlib import Path


def load_agent_toml(path: str | None = None) -> dict:
    target = Path(path) if path else Path("agent.toml")
    if not target.is_file():
        return {}
    try:
        with target.open("rb") as fh:
            data = tomllib.load(fh)
            return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def resolve_config(args, toml_path: str | None = None) -> dict:
    toml = load_agent_toml(toml_path)
    agent_cfg = toml.get("agent", {}) if isinstance(toml, dict) else {}
    llm_cfg = toml.get("llm", {}) if isinstance(toml, dict) else {}

    cfg: dict = {
        "interactive": bool(agent_cfg.get("interactive", False)),
        "use_browser": bool(agent_cfg.get("use_browser", True)),
        "headless": bool(agent_cfg.get("headless", True)),
        "max_steps": int(agent_cfg.get("max_steps", 40) or 40),
        "review_gates": bool(agent_cfg.get("review_gates", False)),
        "stream": bool(agent_cfg.get("stream", False)),
        "sandbox": bool(agent_cfg.get("sandbox", False)),
        "log_file": str(agent_cfg.get("log_file", "agent_run.log")),
        "model": str(llm_cfg.get("model", "") or ""),
        "provider": str(llm_cfg.get("provider", "") or ""),
        "api_base": str(llm_cfg.get("api_base", "") or ""),
    }

    env_overrides = {
        "model": os.getenv("AGENT_MODEL"),
        "provider": os.getenv("AGENT_PROVIDER"),
        "api_base": os.getenv("AGENT_API_BASE"),
    }
    for key, value in env_overrides.items():
        if value:
            cfg[key] = value

    if getattr(args, "interactive", False):
        cfg["interactive"] = True
    if getattr(args, "no_browser", False):
        cfg["use_browser"] = False
    if getattr(args, "show_browser", False):
        cfg["headless"] = False
    if getattr(args, "max_steps", None):
        cfg["max_steps"] = int(args.max_steps)
    if getattr(args, "model", None):
        cfg["model"] = args.model
    if getattr(args, "review_gates", False):
        cfg["review_gates"] = True
    if getattr(args, "stream", False):
        cfg["stream"] = True
    if getattr(args, "sandbox", False):
        cfg["sandbox"] = True
    if getattr(args, "log", None):
        cfg["log_file"] = args.log

    for var, key in (("AGENT_PROVIDER", "provider"), ("AGENT_API_BASE", "api_base"), ("AGENT_MODEL", "model")):
        if cfg[key] and not os.getenv(var):
            os.environ[var] = cfg[key]
    return cfg
