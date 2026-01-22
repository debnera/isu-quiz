import os
import ctypes
import customtkinter as ctk

from quiz_penalties import QuizLoader, PenaltiesQuizScreen, resource_path as quiz_resource_path
from quiz_goe_plus_bullets import RecallQuizLoader, RecallQuizScreen, resource_path as recall_resource_path
from version_update_checker import check_and_prompt_update_async

try:
    from app_version import __version__
except Exception:
    __version__ = "0.0.0+unknown"

VERSION = __version__
APPID = f'debnera.skating.quiz.{VERSION}'
GITHUB_OWNER = "debnera"
GITHUB_REPO = "isu-quiz"


class SkatingApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        if os.name == "nt":
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APPID)

        ctk.set_appearance_mode("dark")
        self.title(f"Skating Trainer {VERSION}")
        self.geometry("1300x1200")

        self._current_screen: ctk.CTkFrame | None = None
        self.show_main_menu()
        check_and_prompt_update_async(self, GITHUB_OWNER, GITHUB_REPO, VERSION)


    def _set_screen(self, screen: ctk.CTkFrame) -> None:
        if self._current_screen is not None:
            self._current_screen.destroy()
        self._current_screen = screen
        self._current_screen.pack(fill="both", expand=True)

    def show_main_menu(self) -> None:
        self._set_screen(MainMenuScreen(self, on_pick=self.start_route))

    def start_route(self, discipline: str, mode: str) -> None:
        # Only pair is implemented right now.
        if discipline != "pair":
            self._set_screen(NotImplementedScreen(self, on_back=self.show_main_menu))
            return

        if mode == "penalties":
            data_file = quiz_resource_path("quiz_data/pair-skating-minus.csv")
            loader = QuizLoader(data_file)
            self._set_screen(PenaltiesQuizScreen(self, loader=loader, on_back=self.show_main_menu))
            return

        if mode == "recall":
            data_file = recall_resource_path("quiz_data/pair-skating-plus.csv")
            loader = RecallQuizLoader(data_file)
            self._set_screen(RecallQuizScreen(self, loader=loader, on_back=self.show_main_menu))
            return

        self._set_screen(NotImplementedScreen(self, on_back=self.show_main_menu))


class MainMenuScreen(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, on_pick):
        super().__init__(master)
        self.on_pick = on_pick

        ctk.CTkLabel(self, text="Choose a mode", font=("Arial", 28, "bold")).pack(pady=(35, 10))

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(pady=25)

        def add_btn(text: str, discipline: str, mode: str, r: int, c: int, enabled: bool):
            btn = ctk.CTkButton(
                grid,
                text=text,
                width=320,
                height=55,
                command=(lambda: self.on_pick(discipline, mode)) if enabled else None
            )
            if not enabled:
                btn.configure(state="disabled")
            btn.grid(row=r, column=c, padx=14, pady=12, sticky="ew")

        # Penalties column
        add_btn("Pair skating penalties", "pair", "penalties", 0, 0, True)
        add_btn("Solo skating penalties", "solo", "penalties", 1, 0, False)
        add_btn("ETC penalties",          "etc",  "penalties", 2, 0, False)

        # Recall column
        add_btn("Pair skating recall", "pair", "recall", 0, 1, True)
        add_btn("Solo skating recall", "solo", "recall", 1, 1, False)
        add_btn("ETC recall",          "etc",  "recall", 2, 1, False)


class NotImplementedScreen(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, on_back):
        super().__init__(master)
        ctk.CTkLabel(self, text="Not implemented yet", font=("Arial", 26, "bold")).pack(pady=(60, 10))
        ctk.CTkLabel(self, text="Only Pair skating is available right now.",
                     font=("Arial", 14), text_color="gray80").pack(pady=(0, 25))
        ctk.CTkButton(self, text="Back to menu", command=on_back, width=220, height=45).pack()


if __name__ == "__main__":
    SkatingApp().mainloop()
