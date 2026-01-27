import csv
import os
import random
import re
import sys
import ctypes
import difflib
import tkinter as tk
import customtkinter as ctk
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

try:
    from PIL import Image
except Exception:
    Image = None

try:
    from app_version import __version__
except Exception:
    __version__ = "0.0.0+unknown"

VERSION = __version__
APPID = f'debnera.skating.quiz.{VERSION}'
WATERMARK_TEXT = f"Build: {VERSION} \t||\t Based on ISU Communication No. 2701 (2025/26)"

# ----------------------------
# Utilities
# ----------------------------

def resource_path(relative_path: str) -> str:
    try:
        base_path = sys._MEIPASS  # type: ignore[attr-defined]
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

_WORD_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)

def normalize_for_compare(text: str) -> str:
    # Lowercase, remove punctuation-ish noise, normalize whitespace.
    text = text.lower()
    text = text.replace("’", "'").replace("–", "-").replace("—", "-")
    text = re.sub(r"[\(\)\[\]\{\}]", " ", text)
    text = re.sub(r"[^a-z0-9\s']", " ", text)  # keep letters/numbers/spaces/apostrophe
    text = re.sub(r"\s+", " ", text).strip()
    return text

def tokenize(text: str) -> List[str]:
    return _WORD_RE.findall(normalize_for_compare(text))

def token_variants(tok: str) -> List[str]:
    # Very lightweight plural tolerance:
    # - cats -> cat
    # - bodies -> body
    # Keeps original too.
    out = [tok]
    if len(tok) > 3:
        if tok.endswith("ies") and len(tok) > 4:
            out.append(tok[:-3] + "y")
        if tok.endswith("s") and not tok.endswith("ss"):
            out.append(tok[:-1])
    seen = set()
    uniq = []
    for t in out:
        if t and t not in seen:
            seen.add(t)
            uniq.append(t)
    return uniq

def build_token_presence_set(tokens: List[str]) -> set:
    s = set()
    for tok in tokens:
        for v in token_variants(tok):
            s.add(v)
    return s

def similarity(user_text: str, correct_text: str) -> float:
    # Blend character similarity (typos) + token overlap (word-level robustness).
    u = normalize_for_compare(user_text)
    c = normalize_for_compare(correct_text)

    if not u and not c:
        return 1.0
    if not u or not c:
        return 0.0

    char_ratio = difflib.SequenceMatcher(None, u, c).ratio()

    utoks = tokenize(user_text)
    ctoks = tokenize(correct_text)
    uset = build_token_presence_set(utoks)
    cset = build_token_presence_set(ctoks)

    if not uset and not cset:
        token_score = 1.0
    elif not uset or not cset:
        token_score = 0.0
    else:
        token_score = len(uset & cset) / len(uset | cset)

    return 0.65 * char_ratio + 0.35 * token_score

def group_of_index(i: int) -> int:
    # Expected indices are 0..5. Group 0 is top 3, group 1 is last 3.
    return 0 if i < 3 else 1

# ----------------------------
# Data model / loading
# ----------------------------

@dataclass(frozen=True)
class RecallItemSet:
    # One quiz unit: 6 ordered descriptions for a component/category.
    category: str
    descriptions: List[str]  # length 6 (ordered)

class RecallQuizLoader:
    # Loads a CSV where each row is:
    #     Category ; Description
    #
    # With the project rule:
    #   - Each category has exactly 6 descriptions (no more, no less).
    #   - Descriptions may optionally be prefixed with "1) ...", ..., "6) ...".
    def __init__(self, filename: str):
        self.filename = filename
        self.sets_by_category: Dict[str, List[RecallItemSet]] = {}
        self._load()

    def _load(self) -> None:
        if not os.path.exists(self.filename):
            raise FileNotFoundError(self.filename)

        rows: List[Tuple[str, str]] = []
        with open(self.filename, mode="r", encoding="ANSI") as f:
            reader = csv.reader(f, delimiter=";")
            for row in reader:
                if len(row) < 2:
                    continue
                cat = row[0].strip()
                desc = row[1].strip()
                if not cat or not desc:
                    continue
                if cat.lower() in {"element category", "category"}:
                    continue
                rows.append((cat, desc))

        by_cat: Dict[str, List[str]] = {}
        for cat, desc in rows:
            by_cat.setdefault(cat, []).append(desc)

        for cat, descs in by_cat.items():
            item_set = self._parse_exact_six(cat, descs)
            self.sets_by_category[cat] = [item_set]

    def _parse_exact_six(self, category: str, descs: List[str]) -> RecallItemSet:
        number_re = re.compile(r"^\s*([1-6])\)\s*(.+?)\s*$")

        if len(descs) != 6:
            raise ValueError(
                f"Category '{category}' must have exactly 6 descriptions, found {len(descs)}"
            )

        parsed: List[Optional[str]] = [None] * 6
        saw_numbering = False

        for raw in descs:
            m = number_re.match(raw)
            if m:
                saw_numbering = True
                idx = int(m.group(1)) - 1
                parsed[idx] = m.group(2).strip()
            else:
                # no numbering on this row; keep in original order (temporarily)
                # we'll finalize below depending on whether numbering existed
                pass

        if saw_numbering:
            # Require all 1..6 to be present exactly once
            if any(x is None for x in parsed):
                raise ValueError(
                    f"Category '{category}' uses numbering but is missing one of 1)..6)"
                )
            return RecallItemSet(category=category, descriptions=[x for x in parsed if x is not None])

        # No numbering: keep original order, just strip any whitespace
        cleaned = [d.strip() for d in descs]
        return RecallItemSet(category=category, descriptions=cleaned)

    def get_categories(self) -> List[str]:
        return sorted(self.sets_by_category.keys())

    def get_sets_for_category(self, category: str) -> List[RecallItemSet]:
        return self.sets_by_category.get(category, [])


# ----------------------------
# Matching / explanation
# ----------------------------

@dataclass
class MatchResult:
    user_slot: int            # 0..5
    matched_correct: Optional[int]  # 0..5 or None
    sim: float

def best_assignment(user_texts: List[str], correct_texts: List[str]) -> List[MatchResult]:
    # Compute best one-to-one assignment (size 6) with a learning-friendly objective:
    #
    # Priority (highest to lowest):
    #   1) remember all descriptions (maximize similarity)
    #   2) correct group (top3 vs last3)
    #   3) correct exact order inside group
    #
    # We allow cross-group "steal" but with penalty.
    n = 6
    sims = [[similarity(user_texts[i], correct_texts[j]) for j in range(n)] for i in range(n)]

    # Penalties are tuned to *nudge* behavior without making it feel like grading.
    GROUP_PENALTY = 0.12
    POS_PENALTY = 0.06

    best_score = -1e9
    best_perm: Optional[Tuple[int, ...]] = None

    # brute force all permutations of mapping user_slot -> correct_index
    # 6! = 720, totally fine.
    import itertools
    for perm in itertools.permutations(range(n)):
        score = 0.0
        for user_i, corr_j in enumerate(perm):
            s = sims[user_i][corr_j]
            if s < 0.45:
                # Treat very low matches as basically not helpful; still allow assignment but it won't win.
                s *= 0.2

            # group penalty
            if group_of_index(user_i) != group_of_index(corr_j):
                s -= GROUP_PENALTY

            # exact position penalty (within group)
            if user_i != corr_j:
                s -= POS_PENALTY

            score += s

        if score > best_score:
            best_score = score
            best_perm = perm

    results: List[MatchResult] = []
    assert best_perm is not None
    for i, j in enumerate(best_perm):
        results.append(MatchResult(user_slot=i, matched_correct=j, sim=sims[i][j]))
    return results


# ----------------------------
# UI (Screen)
# ----------------------------

class RecallQuizScreen(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, loader: "RecallQuizLoader", on_back):
        super().__init__(master)

        # Optional; main app sets its own AppUserModelID already.
        if os.name == "nt":
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APPID)
            except Exception:
                pass

        self.on_back = on_back
        self.loader = loader

        # icon (apply to the root/master, not the frame)
        try:
            if os.name == "nt":
                icon_path = resource_path("skating.ico")
                if os.path.exists(icon_path):
                    master.iconbitmap(icon_path)
        except Exception:
            pass

        self.current_set: Optional["RecallItemSet"] = None
        self.entries: List[ctk.CTkEntry] = []
        self.status_labels: List[ctk.CTkLabel] = []

        # Inline per-row highlight widgets (one per entry)
        self.inline_highlights: List[tk.Text] = []

        # Bottom reference: correct answers in order (labels updated on Check)
        self.correct_ref_frame: Optional[ctk.CTkScrollableFrame] = None
        self.correct_ref_labels: List[ctk.CTkLabel] = []

        # Visual palette for in-place grading (entry borders)
        self.COLOR_OK = "#4CAF50"
        self.COLOR_WARN = "#FFD54F"
        self.COLOR_MID = "#FF9800"
        self.COLOR_BAD = "#F44336"
        self.COLOR_BORDER_DEFAULT = "#3a3a3a"

        self.setup_category_selection()

    def draw_watermark(self) -> None:
        ctk.CTkLabel(self, text=WATERMARK_TEXT, font=("Arial", 10),
                     text_color="gray50").place(relx=0.98, rely=0.98, anchor="se")

    def draw_logo(self) -> None:
        if Image is None:
            return
        try:
            logo_path = resource_path("skating.png")
            if not os.path.exists(logo_path):
                return
            img = Image.open(logo_path)
            logo = ctk.CTkImage(light_image=img, dark_image=img, size=(80, 80))
            ctk.CTkLabel(self, image=logo, text="").place(x=20, y=20)
            self._logo_ref = logo
        except Exception:
            pass

    def clear_screen(self) -> None:
        for widget in self.winfo_children():
            widget.destroy()

    def setup_category_selection(self) -> None:
        self.clear_screen()
        self.draw_watermark()
        self.draw_logo()

        ctk.CTkLabel(self, text="Recall Mode: Positive Descriptions",
                     font=("Arial", 24, "bold")).pack(pady=(25, 10))

        ctk.CTkLabel(
            self,
            text="Type the 6 descriptions from memory. Typos/punctuation/plural forms are OK.",
            font=("Arial", 14),
            text_color="gray80"
        ).pack(pady=(0, 10))

        ctk.CTkButton(self, text="Back to menu", command=self.on_back).pack(pady=(0, 15))

        scroll = ctk.CTkScrollableFrame(self, width=700, height=520)
        scroll.pack(pady=10)

        for cat in self.loader.get_categories():
            sets_count = len(self.loader.get_sets_for_category(cat))
            label = f"{cat}  ({sets_count} set{'s' if sets_count != 1 else ''})"
            ctk.CTkButton(scroll, text=label, height=40,
                          command=lambda c=cat: self.start_quiz(c)).pack(pady=6, fill="x", padx=20)

    def start_quiz(self, category: str) -> None:
        sets = self.loader.get_sets_for_category(category)
        if not sets:
            return
        self.current_set = random.choice(sets)
        self.show_recall_screen()

    def show_recall_screen(self) -> None:
        assert self.current_set is not None

        self.clear_screen()
        self.draw_watermark()

        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", pady=(10, 0), padx=12)
        ctk.CTkButton(top_bar, text="Back to menu", command=self.on_back, width=140).pack(side="left")

        ctk.CTkLabel(self, text=self.current_set.category,
                     font=("Arial", 18, "italic"), text_color="gray70").pack(pady=(10, 5))

        ctk.CTkLabel(self, text="Write all 6 positive descriptions",
                     font=("Arial", 22, "bold")).pack(pady=(0, 10))

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=10)

        # Two groups: top3 and last3
        top_frame = ctk.CTkFrame(container)
        top_frame.pack(fill="x", padx=10, pady=(5, 10))
        ctk.CTkLabel(top_frame, text="Most important (1–3)", font=("Arial", 16, "bold")).pack(anchor="w", padx=12, pady=(10, 0))

        bottom_frame = ctk.CTkFrame(container)
        bottom_frame.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkLabel(bottom_frame, text="Additional (4–6)", font=("Arial", 16, "bold")).pack(anchor="w", padx=12, pady=(10, 0))

        self.entries = []
        self.status_labels = []
        self.inline_highlights = []

        def add_row(parent: ctk.CTkFrame, idx: int) -> None:
            row = ctk.CTkFrame(parent, fg_color="transparent")
            row.pack(fill="x", padx=12, pady=8)

            ctk.CTkLabel(row, text=f"{idx+1}.", width=30, anchor="w",
                         font=("Arial", 14, "bold")).pack(side="left")

            mid = ctk.CTkFrame(row, fg_color="transparent")
            mid.pack(side="left", fill="x", expand=True, padx=(8, 10))

            ent = ctk.CTkEntry(mid, height=34)
            ent.pack(side="top", fill="x", expand=True)

            txt = tk.Text(
                mid,
                height=2,
                wrap="word",
                bg="#1f1f1f",
                fg="#e0e0e0",
                insertbackground="#e0e0e0",
                relief="flat",
                padx=6,
                pady=4
            )
            txt.pack(side="top", fill="x", expand=True, pady=(6, 0))
            txt.tag_configure("good", foreground=self.COLOR_OK)
            txt.tag_configure("bad", foreground=self.COLOR_BAD)
            txt.tag_configure("neutral", foreground="#e0e0e0")
            txt.configure(state="disabled")

            status = ctk.CTkLabel(row, text="", width=260, anchor="w", font=("Arial", 13))
            status.pack(side="left")

            self.entries.append(ent)
            self.inline_highlights.append(txt)
            self.status_labels.append(status)

        for i in range(3):
            add_row(top_frame, i)
        for i in range(3, 6):
            add_row(bottom_frame, i)

        self._reset_entry_styles()
        self._clear_inline_highlights()

        controls = ctk.CTkFrame(container, fg_color="transparent")
        controls.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkButton(controls, text="Check", command=self.on_check).pack(side="left", padx=(0, 10))

        ctk.CTkButton(controls, text="Back to categories",
                      command=self.setup_category_selection).pack(side="right")

        self.correct_ref_frame = ctk.CTkScrollableFrame(container, height=220)
        self.correct_ref_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        ctk.CTkLabel(self.correct_ref_frame, text="Correct order (reference):",
                     font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=(10, 6))

        self.correct_ref_labels = []
        for i in range(6):
            lbl = ctk.CTkLabel(self.correct_ref_frame, text=f"{i+1}.",
                               font=("Arial", 13), text_color="gray80",
                               wraplength=920, justify="left")
            lbl.pack(anchor="w", padx=20, pady=2)
            self.correct_ref_labels.append(lbl)

        self.entries[0].focus_set()

    def _reset_entry_styles(self) -> None:
        # Return all entry boxes to a neutral look.
        for ent in self.entries:
            try:
                ent.configure(border_color=self.COLOR_BORDER_DEFAULT)
            except Exception:
                pass

    def _clear_inline_highlights(self) -> None:
        for txt in self.inline_highlights:
            txt.configure(state="normal")
            txt.delete("1.0", "end")
            txt.insert("end", "Highlight will appear here after Check.", "neutral")
            txt.configure(state="disabled")

    def _fill_inline_highlight(self, row_index: int, user_text: str, correct_text: str) -> None:
        # Render user's text with per-word colors compared to correct_text.
        txt = self.inline_highlights[row_index]
        txt.configure(state="normal")
        txt.delete("1.0", "end")

        other_set = build_token_presence_set(tokenize(correct_text))
        parts = re.findall(r"[A-Za-z0-9']+|[^A-Za-z0-9']+", user_text)

        for part in parts:
            if _WORD_RE.fullmatch(part.strip()):
                tok = normalize_for_compare(part).strip("'")
                present = any(v in other_set for v in token_variants(tok))
                txt.insert("end", part, "good" if present else "bad")
            else:
                txt.insert("end", part, "neutral")

        if not user_text.strip():
            txt.insert("end", " ", "neutral")

        txt.configure(state="disabled")

    def on_check(self) -> None:
        assert self.current_set is not None
        user_texts = [e.get().strip() for e in self.entries]
        correct = self.current_set.descriptions

        matches = best_assignment(user_texts, correct)

        # Update row statuses + entry border colors + INLINE word highlights
        for m in matches:
            i = m.user_slot
            j = m.matched_correct
            sim = m.sim

            if not user_texts[i]:
                self.status_labels[i].configure(text="Blank", text_color=self.COLOR_BAD)
                try:
                    self.entries[i].configure(border_color=self.COLOR_BAD)
                except Exception:
                    pass
                self._fill_inline_highlight(i, "", "")
                continue

            if sim < 0.55 or j is None:
                self.status_labels[i].configure(text="Not close", text_color=self.COLOR_BAD)
                try:
                    self.entries[i].configure(border_color=self.COLOR_BAD)
                except Exception:
                    pass
                # Still show something: compare to the same-slot correct as a hint
                self._fill_inline_highlight(i, user_texts[i], correct[i])
                continue

            same_group = (group_of_index(i) == group_of_index(j))
            if i == j:
                self.status_labels[i].configure(text=f"Matches #{j+1} (correct spot)", text_color=self.COLOR_OK)
                try:
                    self.entries[i].configure(border_color=self.COLOR_OK)
                except Exception:
                    pass
            elif same_group:
                self.status_labels[i].configure(text=f"Matches #{j+1} (wrong order)", text_color=self.COLOR_WARN)
                try:
                    self.entries[i].configure(border_color=self.COLOR_WARN)
                except Exception:
                    pass
            else:
                self.status_labels[i].configure(text=f"Matches #{j+1} (wrong group)", text_color=self.COLOR_MID)
                try:
                    self.entries[i].configure(border_color=self.COLOR_MID)
                except Exception:
                    pass

            # Inline word highlight: YOUR text vs the matched correct description
            self._fill_inline_highlight(i, user_texts[i], correct[j])

        # Bottom reference: show correct answers in order ONLY
        if self.correct_ref_labels:
            for idx, txt in enumerate(correct):
                self.correct_ref_labels[idx].configure(text=f"{idx+1}. {txt}")

    def _render_highlighted_text(self, parent: ctk.CTkFrame, base_text: str, other_text: str, mode: str) -> None:
        # Word-level highlight:
        # - In 'user' mode: green = words that appear in correct (plural-tolerant), red = extra words
        # - In 'correct' mode: green = words present in user, red = missing words
        txt = tk.Text(parent, height=2, wrap="word", bg="#1f1f1f", fg="#e0e0e0",
                      insertbackground="#e0e0e0", relief="flat")
        txt.pack(fill="x", expand=True, padx=8, pady=(0, 8))

        txt.tag_configure("good", foreground="#4CAF50")
        txt.tag_configure("bad", foreground="#F44336")
        txt.tag_configure("neutral", foreground="#e0e0e0")

        base_tokens = tokenize(base_text)
        other_tokens = tokenize(other_text)

        other_set = build_token_presence_set(other_tokens)

        # Render using original-ish spacing by splitting base_text into word/non-word chunks.
        parts = re.findall(r"[A-Za-z0-9']+|[^A-Za-z0-9']+", base_text)
        for part in parts:
            if _WORD_RE.fullmatch(part.strip()):
                tok = normalize_for_compare(part)
                tok = tok.strip("'")
                present = any(v in other_set for v in token_variants(tok))
                tag = "good" if present else "bad"
                txt.insert("end", part, tag)
            else:
                txt.insert("end", part, "neutral")

        txt.configure(state="disabled")

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    # Standalone runner (optional; keep for quick testing)
    ctk.set_appearance_mode("dark")
    root = ctk.CTk()
    root.title(f"Skating Recall Quiz {VERSION}")
    root.geometry("1200x1000")

    data_file = resource_path("quiz_data/pair-skating-plus.csv")
    loader = RecallQuizLoader(data_file)
    if not loader.get_categories():
        raise RuntimeError("No categories/sets found in the plus CSV. Check format and encoding.")

    RecallQuizScreen(root, loader=loader, on_back=root.destroy).pack(fill="both", expand=True)
    root.mainloop()


if __name__ == "__main__":
    main()