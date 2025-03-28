import sys
from PyQt6.QtWidgets import QApplication

# Import the main window class from our ui module
from ui.main_window import SimpleGitApp

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = SimpleGitApp()
    window.show()
    sys.exit(app.exec())
