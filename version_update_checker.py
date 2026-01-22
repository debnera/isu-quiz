import json
import re
import json
import re
import threading
import webbrowser
from urllib.request import Request, urlopen

import customtkinter as ctk

def check_and_prompt_update_async(root, owner: str, repo: str, current_version: str, delay_ms: int = 200) -> None:
    # Starts a background thread to check for updates - prompt user if update is available.
    def start_worker() -> None:
        def worker() -> None:
            available, latest_tag = _is_update_available(owner, repo, current_version)
            if available and latest_tag:
                try:
                    root.after(
                        0,
                        lambda: _show_non_blocking_update_window(root, owner, repo, current_version, latest_tag),
                    )
                except Exception:
                    return

        threading.Thread(target=worker, daemon=True).start()

    try:
        root.after(delay_ms, start_worker)
    except Exception:
        return


def _parse_semantic_version(tag: str) -> tuple[int, int, int] | None:
    # Accepts: v0.1.2, 0.1.2, v0.1.2-3-g<hash> ...
    # Returns (major, minor, patch) or None.
    m = re.search(r"v?(\d+)\.(\d+)\.(\d+)", tag)
    if not m:
        return None
    return int(m.group(1)), int(m.group(2)), int(m.group(3))


def _github_latest_release_tag(owner: str, repo: str) -> str | None:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    req = Request(url, headers={"User-Agent": f"{repo}-update-check"})
    with urlopen(req, timeout=10) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data.get("tag_name")


def _is_update_available(owner: str, repo: str, current_version: str) -> tuple[bool, str | None]:
    # Network-only check. Fail-silent.
    # Returns: (available, latest_tag)
    try:
        latest_tag = _github_latest_release_tag(owner, repo)
        if not latest_tag:
            return False, None

        latest = _parse_semantic_version(latest_tag)
        current = _parse_semantic_version(current_version)

        if not latest or not current:
            return False, None

        return latest > current, latest_tag
    except Exception:
        return False, None


def _show_non_blocking_update_window(root, owner: str, repo: str, current_version: str, latest_tag: str) -> None:
    # Create a non-modal window so the user can ignore it.
    release_url = f"https://github.com/{owner}/{repo}/releases"

    # Avoid multiple windows if check runs more than once.
    existing = getattr(root, "_update_window", None)
    try:
        if existing is not None and bool(existing.winfo_exists()):
            existing.lift()
            existing.focus_force()
            return
    except Exception:
        pass

    win = ctk.CTkToplevel(root)
    root._update_window = win  # type: ignore[attr-defined]

    win.title("Skating Penalty Quiz Update")
    win.transient(root)
    win.resizable(False, False)

    def close() -> None:
        try:
            win.destroy()
        except Exception:
            pass

    win.protocol("WM_DELETE_WINDOW", close)

    container = ctk.CTkFrame(win)
    container.pack(fill="both", expand=True, padx=14, pady=12)

    msg = (
        "A new version is available.\n\n"
        f"Installed: {current_version}\n"
        f"Latest: {latest_tag}\n\n"
    )
    ctk.CTkLabel(container, text=msg, justify="left").pack(anchor="w")

    btn_row = ctk.CTkFrame(container, fg_color="transparent")
    btn_row.pack(fill="x", pady=(12, 0))

    def open_page() -> None:
        try:
            webbrowser.open(release_url)
        finally:
            close()

    ctk.CTkButton(btn_row, text="Open download page", command=open_page).pack(side="left", padx=(0, 8))
    ctk.CTkButton(btn_row, text="Not now", command=close).pack(side="right")
