import subprocess
from pathlib import Path

OUT_FILE = Path(__file__).resolve().parents[1] / "app_version.py"

def git_version() -> str:
    try:
        v = subprocess.check_output(
            ["git", "describe", "--tags", "--dirty", "--always"],
            text=True,
            stderr=subprocess.STDOUT,
        ).strip()
        return v
    except Exception:
        return "0.0.0+nogit"

def write_version() -> str:
    version = git_version()
    OUT_FILE.write_text(f'__version__ = "{version}"\n', encoding="utf-8")
    print(f"Wrote version: {version} -> {OUT_FILE}")
    return version

def main() -> None:
    write_version()

if __name__ == "__main__":
    main()
