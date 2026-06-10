"""Sync APP_VERSION in .env with the version in pyproject.toml."""
import pathlib
import tomllib

ROOT = pathlib.Path(__file__).resolve().parent.parent
version = tomllib.load((ROOT / "pyproject.toml").open("rb"))["project"]["version"]

env_path = ROOT / ".env"
lines = [
    line for line in env_path.read_text().splitlines()
    if not line.startswith("APP_VERSION=")
] if env_path.exists() else []
lines.append(f"APP_VERSION={version}")
env_path.write_text("\n".join(lines) + "\n")

print(version)
