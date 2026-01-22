# Ice skating quiz

A simple quiz game for learning very specific ice skating rules for a very specific ice skating exam.


## Creating executable with pyinstaller

    pyinstaller --noconsole --onefile --add-data "quiz_data;quiz_data" --add-data "skating.png;." --add-data "skating.ico;." --icon=skating.ico skating_quiz.py