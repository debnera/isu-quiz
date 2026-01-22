import csv
import os
import random
import customtkinter as ctk
import sys
import ctypes
from PIL import Image

try:
    from app_version import __version__
except Exception:
    __version__ = "0.0.0+unknown"
VERSION = __version__
WATERMARK_TEXT = f"Build: {VERSION} \t||\t Based on ISU Communication No. 2701 (2025/26)"
APPID = f'debnera.skating.quiz.{VERSION}'

# --- Data Layer ---
class QuizLoader:
    def __init__(self, filename):
        self.filename = filename
        self.data = {}
        self.all_possible_answers = set()
        self.load_data()

    def load_data(self):
        if not os.path.exists(self.filename):
            print(f"Error: {self.filename} not found.")
            return

        try:
            with open(self.filename, mode='r', encoding='ANSI') as f:
                reader = csv.reader(f, delimiter=';')
                next(reader, None) # Skip header

                for row in reader:
                    if len(row) >= 3:
                        category = row[0].strip()
                        description = row[1].strip()
                        answer = row[2].strip()

                        if category not in self.data:
                            self.data[category] = []

                        self.data[category].append({
                            'question': description,
                            'answer': answer
                        })
                        self.all_possible_answers.add(answer)
        except Exception as e:
            print(f"Error reading file: {e}")

    def get_categories(self):
        return sorted(list(self.data.keys()))

    def get_questions(self, category):
        return self.data.get(category, [])

    def get_all_answers(self):
        return sorted(list(self.all_possible_answers))

# --- Logic Layer ---
class QuizEngine:
    def __init__(self, questions):
        self.questions = questions
        self.current_index = 0
        self.score = 0
        self.attempts_on_current = 0

    def get_current_question(self):
        if self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    def check_answer(self, user_answer):
        correct_answer = self.questions[self.current_index]['answer']
        is_correct = user_answer == correct_answer

        if is_correct:
            if self.attempts_on_current == 0:
                self.score += 1
            self.current_index += 1
            self.attempts_on_current = 0
            return True
        else:
            self.attempts_on_current += 1
            return False

# --- UI Layer (Screen) ---
class PenaltiesQuizScreen(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, loader: QuizLoader, on_back):
        super().__init__(master)

        # Tell Windows this is a separate application to show the taskbar icon correctly
        # (Main app sets its own AppUserModelID; leaving this here is harmless, but optional.)
        if os.name == 'nt':
            try:
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APPID)
            except Exception:
                pass

        self.on_back = on_back

        # Load quiz data
        self.loader = loader
        self.engine = None
        self.possible_answers = self.loader.get_all_answers()

        self.buttons = None
        self.current_category_name = None
        self.feedback_label = None

        self.setup_category_selection()


    def draw_watermark(self):
        ctk.CTkLabel(self, text=WATERMARK_TEXT,
                     font=("Arial", 10), text_color="gray50").place(relx=0.98, rely=0.98, anchor="se")

    def draw_logo(self):
        try:
            logo_path = resource_path("skating.png")
            logo_image = ctk.CTkImage(light_image=Image.open(logo_path),
                                      dark_image=Image.open(logo_path),
                                      size=(100, 100))
            logo_label = ctk.CTkLabel(self, image=logo_image, text="")
            logo_label.place(x=20, y=20)
            self._logo_ref = logo_image  # keep a reference
        except Exception as e:
            print(f"Could not load logo: {e}")

    def clear_screen(self):
        for widget in self.winfo_children():
            widget.destroy()

    def setup_category_selection(self):
        self.clear_screen()
        self.draw_watermark()
        self.draw_logo()

        ctk.CTkLabel(self, text="Select Element Category", font=("Arial", 24, "bold")).pack(pady=30)

        ctk.CTkButton(self, text="Back to menu", command=self.on_back).pack(pady=(0, 10))

        scroll_frame = ctk.CTkScrollableFrame(self, width=500, height=400)
        scroll_frame.pack(pady=10)

        for cat in self.loader.get_categories():
            ctk.CTkButton(scroll_frame, text=cat, height=40,
                          command=lambda c=cat: self.start_quiz(c)).pack(pady=5, fill="x", padx=20)

    def start_quiz(self, category):
        questions = self.loader.get_questions(category).copy()
        random.shuffle(questions)
        self.current_category_name = category
        self.engine = QuizEngine(questions)
        self.show_question()

    def draw_buttons(self):
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(pady=10)
        rows = {}

        found_ints = []
        for val in self.possible_answers:
            base_str = val.split(' ')[0]
            if base_str not in rows:
                rows[base_str] = []
            rows[base_str].append(val)
            try:
                found_ints.append(int(base_str))
            except ValueError:
                pass

        if found_ints:
            min_val = min(found_ints)
            max_val = max(found_ints)
            full_range_bases = [str(i) for i in range(max_val, min_val - 1, -1)]
        else:
            full_range_bases = sorted(rows.keys(), reverse=True)

        self.buttons = {}
        for r_idx, base in enumerate(full_range_bases):
            row_values = rows.get(base, [base])
            row_values = sorted(row_values, key=len)

            for c_idx, val in enumerate(row_values):
                btn = ctk.CTkButton(self.btn_frame, text=val, width=120, height=45,
                                    command=lambda v=val: self.handle_press(v))
                btn.grid(row=r_idx, column=c_idx, padx=8, pady=8)
                self.buttons[val] = btn

    def show_question(self):
        self.clear_screen()
        self.draw_watermark()

        q = self.engine.get_current_question()
        if not q:
            self.show_results()
            return

        top_bar = ctk.CTkFrame(self, fg_color="transparent")
        top_bar.pack(fill="x", pady=(10, 0), padx=12)

        ctk.CTkButton(top_bar, text="Back to menu", command=self.on_back, width=140).pack(side="left")

        ctk.CTkLabel(self, text=self.current_category_name,
                     font=("Arial", 16, "italic"), text_color="gray").pack(pady=(10, 0))

        progress = f"Question {self.engine.current_index + 1} of {len(self.engine.questions)}"
        ctk.CTkLabel(self, text=progress, font=("Arial", 12)).pack(pady=5)

        question_label = ctk.CTkLabel(self, text=q['question'], font=("Arial", 20, "bold"), wraplength=700)
        question_label.pack(pady=30)

        self.draw_buttons()

        self.feedback_label = ctk.CTkLabel(self, text="", font=("Arial", 18, "bold"))
        self.feedback_label.pack(pady=30)

    def handle_press(self, choice):
        is_correct = self.engine.check_answer(choice)

        if is_correct:
            self.feedback_label.configure(text="CORRECT", text_color="#4CAF50")
            for btn in self.buttons.values():
                btn.configure(state="disabled")
            self.buttons[choice].configure(fg_color="#4CAF50")
            self.after(700, self.show_question)
        else:
            self.feedback_label.configure(text="WRONG", text_color="#F44336")
            self.buttons[choice].configure(fg_color="#F44336", state="disabled")

    def show_results(self):
        self.clear_screen()
        self.draw_watermark()
        self.draw_logo()

        ctk.CTkLabel(self, text="Quiz Results", font=("Arial", 32, "bold")).pack(pady=50)
        score_msg = f"Points: {self.engine.score} / {len(self.engine.questions)}"
        ctk.CTkLabel(self, text=score_msg, font=("Arial", 24)).pack(pady=20)

        ctk.CTkButton(self, text="Back to Categories", command=self.setup_category_selection).pack(pady=10)
        ctk.CTkButton(self, text="Back to menu", command=self.on_back).pack(pady=10)


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


if __name__ == "__main__":
    # This module is now intended to be imported by skating_main.py
    data_file = resource_path("quiz_data/pair-skating-minus.csv")
    loader = QuizLoader(data_file)
    if loader.get_categories():
        root = ctk.CTk()
        root.geometry("800x600")
        root.title(f"Skating Penalty Quiz {VERSION}")
        PenaltiesQuizScreen(root, loader=loader, on_back=root.destroy).pack(fill="both", expand=True)
        root.mainloop()