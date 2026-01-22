import shutil
import subprocess
import sys
from write_version import write_version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PYINSTALLER_ARGS = [
    "--noconsole",
    "--add-data", "quiz_data;quiz_data",
    "--add-data", "skating.png;.",
    "--add-data", "skating.ico;.",
    "--icon=skating.ico",
    "-y",  # Delete the previous build directory without asking
    "skating_quiz.py",
]

def run(cmd: list[str]) -> None:
    print(">", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

def main() -> None:
    version = write_version()
    run([sys.executable, "-m", "PyInstaller", *PYINSTALLER_ARGS])
    zip_path = zip_dist(app_name="skating_quiz", version=version)
    print(f"Created: {zip_path}")

def zip_dist(app_name: str, version: str) -> Path:
    dist_dir = ROOT / "dist"

    folder_candidate = dist_dir / app_name
    exe_candidate = dist_dir / f"{app_name}.exe"

    base_name = dist_dir / f"{app_name}-{version}-windows"
    zip_path = base_name.with_suffix(".zip")

    if zip_path.exists():
        zip_path.unlink()

    if folder_candidate.exists() and folder_candidate.is_dir():
        shutil.make_archive(str(base_name), "zip", root_dir=str(dist_dir), base_dir=app_name)
    elif exe_candidate.exists() and exe_candidate.is_file():
        # One-file build: zip just the exe
        shutil.make_archive(str(base_name), "zip", root_dir=str(dist_dir), base_dir=f"{app_name}.exe")
    else:
        raise FileNotFoundError(
            f"Nothing to zip. Expected '{folder_candidate}' or '{exe_candidate}' to exist after PyInstaller."
        )

    return zip_path

if __name__ == "__main__":
    main()