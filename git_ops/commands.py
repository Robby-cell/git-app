# git_ops/commands.py
import subprocess
import os
from PyQt6.QtCore import QThread, pyqtSignal

class GitCommandThread(QThread):
    """Runs a Git command in a separate thread."""
    # Single signal: Emits (thread_instance, success_bool, stdout_str, stderr_str)
    command_finished = pyqtSignal(object, bool, str, str)

    # command_output = pyqtSignal(str) # No longer needed
    # command_error = pyqtSignal(str) # No longer needed

    def __init__(self, command_list, cwd):
        super().__init__()
        self.command_list = command_list
        self.cwd = cwd
        if not self.cwd:
            raise ValueError("Cannot run Git command without a working directory (cwd).")

    def run(self):
        stdout = ""
        stderr = ""
        success = False
        try:
            env = os.environ.copy()
            env['LANG'] = 'C'; env['LC_ALL'] = 'C'

            process = subprocess.run(
                self.command_list, capture_output=True, text=True, check=False,
                cwd=self.cwd, env=env, encoding='utf-8'
            )
            stdout = process.stdout
            stderr = process.stderr
            success = (process.returncode == 0)

        except FileNotFoundError:
             stderr = f"Error: 'git' command not found. Is Git installed and in PATH?"
             success = False
        except Exception as e:
            stderr = f"An unexpected error occurred during git command: {e}"
            success = False
        finally:
            # Emit results regardless of success/failure in run()
            self.command_finished.emit(self, success, stdout, stderr)
