import os
import tomllib
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()  # load .env into os.environ if present

def load_config(path="config.toml"):
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config not found: {p}")
    with open(p, "rb") as f:
        return tomllib.load(f)

def get_env(name, default=None):
    return os.environ.get(name, default)
