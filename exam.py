import csv
import os
import random  # Added for shuffling
import customtkinter as ctk
import sys

# --- Data Layer ---
class QuizLoader:
    def __init__(self, filename):
        self.filename = filename
        self.data = {}
        self.all_possible_answers = set() # To store unique values for buttons
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
        # Return sorted unique answers (e.g., -1, -2, -3, -5)
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

# --- UI Layer ---
class SkatingQuizUI:
    def __init__(self, loader):
        self.loader = loader
        self.engine = None
        self.possible_answers = self.loader.get_all_answers()
        
        ctk.set_appearance_mode("dark")
        self.root = ctk.CTk()
        self.root.title("Skating Penalty Quiz")
        self.root.geometry("800x600")
        self.setup_category_selection()

    def clear_screen(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    def setup_category_selection(self):
        self.clear_screen()
        ctk.CTkLabel(self.root, text="Select Element Category", font=("Arial", 24, "bold")).pack(pady=30)
        
        scroll_frame = ctk.CTkScrollableFrame(self.root, width=500, height=400)
        scroll_frame.pack(pady=10)

        for cat in self.loader.get_categories():
            ctk.CTkButton(scroll_frame, text=cat, height=40,
                          command=lambda c=cat: self.start_quiz(c)).pack(pady=5, fill="x", padx=20)

    def start_quiz(self, category):
        questions = self.loader.get_questions(category).copy()  # Use copy to avoid changing original data
        random.shuffle(questions)  # Shuffles the list in-place
        self.current_category_name = category
        self.engine = QuizEngine(questions)
        self.show_question()

    def show_question(self):
        self.clear_screen()
        q = self.engine.get_current_question()
        if not q:
            self.show_results()
            return

        # Display Category Label above everything else
        ctk.CTkLabel(self.root, text=self.current_category_name, 
                     font=("Arial", 16, "italic"), text_color="gray").pack(pady=(10, 0))

        # Header with progress
        progress = f"Question {self.engine.current_index + 1} of {len(self.engine.questions)}"
        ctk.CTkLabel(self.root, text=progress, font=("Arial", 12)).pack(pady=5)
    
        # Display the Error Description as the question
        question_label = ctk.CTkLabel(self.root, text=q['question'], font=("Arial", 20, "bold"), wraplength=700)
        question_label.pack(pady=30)

        self.btn_frame = ctk.CTkFrame(self.root, fg_color="transparent")
        self.btn_frame.pack(pady=10)

        # --- Dynamic Grid Logic with Gap Filling ---
        rows = {}
        found_ints = []
        
        # 1. Group existing values and track found integers
        for val in self.possible_answers:
            base_str = val.split(' ')[0]
            if base_str not in rows:
                rows[base_str] = []
            rows[base_str].append(val)
            
            try:
                found_ints.append(int(base_str))
            except ValueError:
                pass

        # 2. Determine the full range (e.g., -1 to -5) and fill gaps
        if found_ints:
            min_val = min(found_ints)
            max_val = max(found_ints)
            # Create a sequence from highest to lowest (e.g., -1, -2, -3, -4, -5)
            full_range_bases = [str(i) for i in range(max_val, min_val - 1, -1)]
        else:
            full_range_bases = sorted(rows.keys(), reverse=True)

        self.buttons = {}
        for r_idx, base in enumerate(full_range_bases):
            # Get existing values or just the base if none exist in CSV
            row_values = rows.get(base, [base])
            # Ensure the singular value is always first in the row
            row_values = sorted(row_values, key=len)
            
            for c_idx, val in enumerate(row_values):
                btn = ctk.CTkButton(self.btn_frame, text=val, width=120, height=45,
                                    command=lambda v=val: self.handle_press(v))
                btn.grid(row=r_idx, column=c_idx, padx=8, pady=8)
                self.buttons[val] = btn

        self.feedback_label = ctk.CTkLabel(self.root, text="", font=("Arial", 18, "bold"))
        self.feedback_label.pack(pady=30)

    def handle_press(self, choice):
        is_correct = self.engine.check_answer(choice)
        
        if is_correct:
            self.feedback_label.configure(text="CORRECT", text_color="#4CAF50")
            for btn in self.buttons.values(): btn.configure(state="disabled")
            self.buttons[choice].configure(fg_color="#4CAF50")
            self.root.after(700, self.show_question)
        else:
            self.feedback_label.configure(text="WRONG", text_color="#F44336")
            self.buttons[choice].configure(fg_color="#F44336", state="disabled")

    def show_results(self):
        self.clear_screen()
        ctk.CTkLabel(self.root, text="Quiz Results", font=("Arial", 32, "bold")).pack(pady=50)
        score_msg = f"Points: {self.engine.score} / {len(self.engine.questions)}"
        ctk.CTkLabel(self.root, text=score_msg, font=("Arial", 24)).pack(pady=20)
        ctk.CTkButton(self.root, text="Back to Categories", command=self.setup_category_selection).pack(pady=40)

    def run(self):
        self.root.mainloop()

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# ... inside your __main__ block ...
if __name__ == "__main__":
    # Use the resource_path helper here!
    data_file = resource_path("quiz_data/pair-skating-minus.csv")
    loader = QuizLoader(data_file)
    if loader.get_categories():
        app = SkatingQuizUI(loader)
        app.run()