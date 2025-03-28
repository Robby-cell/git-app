# ui/main_window.py
import sys
import os
from PyQt6.QtWidgets import (QMainWindow, QTextEdit, QVBoxLayout, QSizePolicy,
                             QWidget, QPushButton, QFileDialog, QLabel,
                             QListWidget, QHBoxLayout, QSplitter, QFrame,
                             QApplication, QMenu, QMessageBox,
                             QTableWidget, QTableWidgetItem, QHeaderView)
from PyQt6.QtCore import Qt, QPoint, QTimer # <<< Added QTimer
from PyQt6.QtGui import QAction

from git_ops.commands import GitCommandThread
from utils.helpers import extract_file_path

GIT_LOG_FORMAT = "%H%x09%an%x09%ad%x09%s"
GIT_LOG_DATE_FORMAT = "iso"
MAX_LOG_COUNT = 200

class SimpleGitApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Python Git GUI - Step 6 Refactored")
        self.setGeometry(100, 100, 950, 700)

        self.repo_path = None
        self.current_git_thread = None
        self.current_operation_name = None # Store name of running operation
        self._output_parser_slot = None   # Store the correct parser for the current op
        self._is_initial_load = False     # Flag for open repo sequence

        self._init_ui()
        self._connect_signals()
        self.update_button_states()

    # --- _init_ui (Largely Unchanged from previous History step) ---
    def _init_ui(self):
        # (Keep the UI layout exactly as in the previous step with History Table)
        self.central_widget=QWidget();self.main_layout=QVBoxLayout(self.central_widget);self.top_bar_layout=QHBoxLayout();self.open_button=QPushButton("Open Repository");self.repo_label=QLabel("No repository opened.");self.repo_label.setWordWrap(True);self.status_button=QPushButton("Refresh Status");self.status_button.setEnabled(False);self.refresh_history_button=QPushButton("Refresh History");self.refresh_history_button.setEnabled(False);self.top_bar_layout.addWidget(self.open_button);self.top_bar_layout.addWidget(self.repo_label,1);self.top_bar_layout.addWidget(self.status_button);self.top_bar_layout.addWidget(self.refresh_history_button);self.main_layout.addLayout(self.top_bar_layout);self.main_splitter=QSplitter(Qt.Orientation.Horizontal);self.status_frame=QFrame();self.status_layout=QVBoxLayout(self.status_frame);self.status_layout.setContentsMargins(5,5,5,5);self.staged_area_layout=QHBoxLayout();self.staged_label=QLabel("Staged Files:");self.unstage_button=QPushButton("Unstage Selected");self.staged_area_layout.addWidget(self.staged_label);self.staged_area_layout.addStretch();self.staged_area_layout.addWidget(self.unstage_button);self.staged_list=QListWidget();self.staged_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection);self.unstaged_area_layout=QHBoxLayout();self.unstaged_label=QLabel("Unstaged Changes:");self.stage_button=QPushButton("Stage Selected");self.unstaged_area_layout.addWidget(self.unstaged_label);self.unstaged_area_layout.addStretch();self.unstaged_area_layout.addWidget(self.stage_button);self.unstaged_list=QListWidget();self.unstaged_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection);self.unstaged_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.untracked_label=QLabel("Untracked Files:");self.untracked_list=QListWidget();self.untracked_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection);self.untracked_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu);self.status_layout.addLayout(self.staged_area_layout);self.status_layout.addWidget(self.staged_list,1);self.status_layout.addLayout(self.unstaged_area_layout);self.status_layout.addWidget(self.unstaged_list,1);self.status_layout.addWidget(self.untracked_label);self.status_layout.addWidget(self.untracked_list,1);self.status_frame.setLayout(self.status_layout);self.right_pane_widget=QWidget();self.right_pane_layout=QVBoxLayout(self.right_pane_widget);self.right_pane_layout.setContentsMargins(0,0,0,0);self.right_splitter=QSplitter(Qt.Orientation.Vertical);self.history_table=QTableWidget();self.history_table.setColumnCount(4);self.history_table.setHorizontalHeaderLabels(["Commit","Author","Date","Subject"]);self.history_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.history_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection);self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.history_table.verticalHeader().setVisible(False);header=self.history_table.horizontalHeader();header.setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents);header.setSectionResizeMode(1,QHeaderView.ResizeMode.Interactive);header.setSectionResizeMode(2,QHeaderView.ResizeMode.Interactive);header.setSectionResizeMode(3,QHeaderView.ResizeMode.Stretch);self.history_table.setMinimumHeight(150);self.commit_area_frame=QFrame();self.commit_layout=QVBoxLayout(self.commit_area_frame);self.commit_layout.setContentsMargins(5,5,5,5);self.commit_label=QLabel("Commit Message:");self.commit_message_box=QTextEdit();self.commit_message_box.setPlaceholderText("Enter commit message here...");self.commit_message_box.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding);self.commit_button=QPushButton("Commit Staged Changes");self.commit_layout.addWidget(self.commit_label);self.commit_layout.addWidget(self.commit_message_box,1);self.commit_layout.addWidget(self.commit_button);self.commit_area_frame.setMinimumHeight(100);self.right_splitter.addWidget(self.history_table);self.right_splitter.addWidget(self.commit_area_frame);self.right_splitter.setSizes([400,200]);self.right_pane_layout.addWidget(self.right_splitter);self.main_splitter.addWidget(self.status_frame);self.main_splitter.addWidget(self.right_pane_widget);self.main_splitter.setSizes([400,550]);self.main_layout.addWidget(self.main_splitter,1);self.error_output_area=QTextEdit();self.error_output_area.setReadOnly(True);self.error_output_area.setMaximumHeight(80);self.main_layout.addWidget(self.error_output_area);self.setCentralWidget(self.central_widget)


    # --- _connect_signals (Unchanged) ---
    def _connect_signals(self):
        # (Keep connections exactly as in the previous History step)
        self.open_button.clicked.connect(self.open_repository);self.status_button.clicked.connect(self.refresh_status);self.refresh_history_button.clicked.connect(self.refresh_history);self.staged_list.itemSelectionChanged.connect(self.update_button_states);self.unstaged_list.itemSelectionChanged.connect(self.update_button_states);self.staged_list.model().rowsInserted.connect(self.update_button_states);self.staged_list.model().rowsRemoved.connect(self.update_button_states);self.commit_message_box.textChanged.connect(self.update_button_states);self.stage_button.clicked.connect(self.stage_selected_files);self.unstage_button.clicked.connect(self.unstage_selected_files);self.commit_button.clicked.connect(self.commit_changes);self.unstaged_list.customContextMenuRequested.connect(self.show_status_context_menu);self.untracked_list.customContextMenuRequested.connect(self.show_status_context_menu)


    # --- Context Menu Slot (Unchanged) ---
    def show_status_context_menu(self, point: QPoint):
        # (Keep exactly as before)
        source_list=self.sender();menu=QMenu(self);#... rest unchanged ...
        if isinstance(source_list,QListWidget):selected_items=source_list.selectedItems();#... rest unchanged ...
        if not menu.isEmpty():menu.exec(source_list.mapToGlobal(point))


    # --- Action Slots (Simplified: just call _start_git_thread) ---

    def open_repository(self):
        if self.current_git_thread: return # Already busy
        path = QFileDialog.getExistingDirectory(self, "Select Git Repository")
        if path:
            git_dir = os.path.join(path, '.git')
            if os.path.isdir(git_dir) or os.path.isfile(git_dir):
                 self.repo_path = path
                 self.repo_label.setText(f"Repository: {self.repo_path}")
                 # Enable buttons - busy state will control them further
                 self.status_button.setEnabled(True)
                 self.refresh_history_button.setEnabled(True)
                 self.clear_all_views()
                 self.error_output_area.clear()
                 self._is_initial_load = True # Set flag for chained loading
                 self.refresh_status() # Start the chain
            else:
                 # Handle invalid path selection
                 self.repo_path = None; self.repo_label.setText("Not a valid Git repository."); self.status_button.setEnabled(False); self.refresh_history_button.setEnabled(False); self.clear_all_views(); self.update_button_states(); self.error_output_area.setText("Selected directory is not a Git repository.")

    def refresh_status(self):
        if not self._can_run_git_command("refresh status"): return
        self.clear_status_lists() # Clear relevant view immediately
        self.error_output_area.setText("Refreshing status...")
        self.set_ui_busy(True)
        command = ['git', 'status', '--porcelain=v1', '--untracked-files=normal']
        # Pass the parser slot for status
        self._start_git_thread(command, "Status", parser_slot=self.parse_and_display_status)

    def refresh_history(self):
        if not self._can_run_git_command("refresh history"): return
        self.clear_history_view() # Clear relevant view immediately
        self.error_output_area.setText("Refreshing history...")
        self.set_ui_busy(True)
        command = ['git', 'log', f'--pretty=format:{GIT_LOG_FORMAT}', f'--date={GIT_LOG_DATE_FORMAT}', f'--max-count={MAX_LOG_COUNT}', 'HEAD']
        # Pass the parser slot for history
        self._start_git_thread(command, "History", parser_slot=self.parse_and_display_history)

    def stage_selected_files(self):
        selected_items = self.unstaged_list.selectedItems()
        if not selected_items or not self._can_run_git_command("stage files"): return
        files = [extract_file_path(item.text()) for item in selected_items]
        if not files: return
        self.error_output_area.setText(f"Staging {len(files)} file(s)..."); self.set_ui_busy(True)
        self._start_git_thread(['git', 'add', '--'] + files, "Stage")

    def unstage_selected_files(self):
        selected_items = self.staged_list.selectedItems()
        if not selected_items or not self._can_run_git_command("unstage files"): return
        files = [extract_file_path(item.text()) for item in selected_items]
        if not files: return
        self.error_output_area.setText(f"Unstaging {len(files)} file(s)..."); self.set_ui_busy(True)
        self._start_git_thread(['git', 'reset', 'HEAD', '--'] + files, "Unstage")

    def discard_selected_files(self, source_list):
        selected_items = source_list.selectedItems()
        if not selected_items or not self._can_run_git_command("discard changes/files"): return
        files = [extract_file_path(item.text()) for item in selected_items]
        if not files: return
        # --- Confirmation Dialog (same as before) ---
        num_files, file_plural = len(files), "file" if len(files) == 1 else "files"; list_sample = f"{files[0]}{f' and {num_files - 1} other(s)' if num_files > 1 else ''}"
        if source_list is self.unstaged_list: confirm_title, confirm_text, command_base, action_name = "Confirm Discard Changes", f"Discard changes to {num_files} {file_plural}?\n({list_sample})", ['git', 'checkout', 'HEAD', '--'], "Discard"
        elif source_list is self.untracked_list: confirm_title, confirm_text, command_base, action_name = "Confirm Delete Untracked Files", f"PERMANENTLY DELETE {num_files} untracked {file_plural}?\n({list_sample})", ['git', 'clean', '-fdx', '--'], "Clean"
        else: return
        reply = QMessageBox.warning(self, confirm_title, confirm_text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Cancel)
        if reply != QMessageBox.StandardButton.Yes: self.error_output_area.setText(f"{action_name} operation cancelled."); return
        # --- END Confirmation ---
        self.error_output_area.setText(f"{action_name}ing files..."); self.set_ui_busy(True)
        self._start_git_thread(command_base + files, action_name)

    def commit_changes(self):
        if not self._can_run_git_command("commit"): return
        if self.staged_list.count() == 0: self.error_output_area.setText("Cannot commit: No files staged."); return
        commit_message = self.commit_message_box.toPlainText().strip()
        if not commit_message: self.error_output_area.setText("Cannot commit: Commit message cannot be empty."); self.commit_message_box.setFocus(); return
        self.error_output_area.setText("Committing staged changes..."); self.set_ui_busy(True)
        self._start_git_thread(['git', 'commit', '-m', commit_message], "Commit")


    # --- Git Command Handling ---

    def _can_run_git_command(self, operation_name="perform Git operation"):
        if not self.repo_path:
            self.error_output_area.setText("No repository open."); return False
        # Check if thread object exists AND is running
        if self.current_git_thread and self.current_git_thread.isRunning():
            # Provide context about the running operation
            running_op = self.current_operation_name or "a Git command"
            self.error_output_area.setText(f"Cannot {operation_name}: {running_op} is already running.")
            return False
        return True

    def _start_git_thread(self, command, operation_name, parser_slot=None): # Removed finished_slot override
        """Creates, configures, and starts a GitCommandThread."""
        try:
            self.current_operation_name = operation_name
            self._output_parser_slot = parser_slot # Store parser for the finished handler

            # Create new thread instance
            thread = GitCommandThread(command, self.repo_path)

            # --- Single connection point ---
            # Disconnect any previous connection from the *variable* (paranoia)
            if self.current_git_thread:
                 try: self.current_git_thread.command_finished.disconnect(self._on_git_command_finished)
                 except TypeError: pass # Ignore if not connected
            # Connect the new thread instance
            thread.command_finished.connect(self._on_git_command_finished)
            # --- END ---

            # Assign to instance variable *before* starting
            self.current_git_thread = thread
            self.current_git_thread.start()

        except Exception as e:
            self.error_output_area.setText(f"Failed to start Git thread for {operation_name}: {e}")
            self.current_operation_name = None
            self.current_git_thread = None
            self._output_parser_slot = None
            # Ensure UI is usable after a failed start
            self.set_ui_busy(False)

    # --- Central Finished Slot ---

    def _on_git_command_finished(self, finished_thread, success, stdout, stderr):
        """Central handler for when any GitCommandThread finishes."""

        # --- Safety Check: Ignore signals from unexpected threads ---
        if finished_thread != self.current_git_thread:
            print(f"Ignoring finished signal from unexpected thread: {finished_thread}")
            # Potentially try to clean up the unexpected thread?
            # finished_thread.quit() # Ask it to stop (might not work if blocked)
            # finished_thread.wait(100) # Wait briefly
            return

        # --- Store info from the finished thread before clearing references ---
        op_name = self.current_operation_name
        parser = self._output_parser_slot
        initial_load_flag = self._is_initial_load # Check initial load status

        print(f"Git command finished: {op_name}, Success: {success}") # Debug

        # --- Immediately clear thread references ---
        # Prevents race conditions if another action is triggered quickly
        self.current_git_thread = None
        self.current_operation_name = None
        self._output_parser_slot = None
        if initial_load_flag and op_name == "Status":
            self._is_initial_load = False # Reset flag after status finishes


        # --- Process results and Handle Errors ---
        error_occurred = not success
        post_action_refresh_status = False
        post_action_refresh_history = False

        if success:
            if parser:
                try:
                    parser(stdout) # Call the specific parser (status or history)
                except Exception as e:
                    self.error_output_area.setText(f"Error processing output for {op_name}: {e}")
                    error_occurred = True
            # Clear simple "Running..." messages if no error and no parser
            elif f"{op_name}..." in self.error_output_area.toPlainText() or \
                 f"{op_name}ing..." in self.error_output_area.toPlainText():
                 self.error_output_area.clear()

            # --- Determine Follow-Up Actions on Success ---
            if op_name == "Commit":
                self.commit_message_box.clear() # Clear message box on successful commit
                post_action_refresh_status = True
                post_action_refresh_history = True
            elif op_name == "Status" and initial_load_flag: # Check flag used before reset
                 post_action_refresh_history = True # Chain to history on initial load
            elif op_name in ["Stage", "Unstage", "Discard", "Clean"]:
                 post_action_refresh_status = True # Refresh status after these actions

            # Update clean message only after successful status refresh
            if op_name == "Status":
                 is_clean = (self.staged_list.count() == 0 and
                             self.unstaged_list.count() == 0 and
                             self.untracked_list.count() == 0)
                 if is_clean:
                      self.error_output_area.setText("Working tree clean.")


        else: # Handle Failure (Error Occurred)
            error_message = f"Error during {op_name}:\n{stderr.strip()}"
            if not stderr.strip() and stdout.strip():
                error_message += f"\nOutput:\n{stdout.strip()}"
            self.error_output_area.setText(error_message)


        # --- Trigger Post Actions using QTimer ---
        # Use QTimer to yield to the event loop before starting next command
        if post_action_refresh_status:
             print(f"Queueing post-action: refresh_status (after {op_name})")
             QTimer.singleShot(10, self.refresh_status) # Small delay
        if post_action_refresh_history:
             print(f"Queueing post-action: refresh_history (after {op_name})")
             QTimer.singleShot(10, self.refresh_history) # Small delay


        # --- Update UI Busy State ---
        # If post actions are queued, the UI remains effectively busy until they run.
        # If no post actions, make the UI not busy immediately.
        if not post_action_refresh_status and not post_action_refresh_history:
             print(f"Operation {op_name} finished, no post actions, setting UI not busy.")
             QTimer.singleShot(0, lambda: self.set_ui_busy(False))
        else:
             # If actions are queued, just update button states, don't fully unlock UI yet.
             # The subsequent actions will call set_ui_busy(False) when they finish.
             print(f"Operation {op_name} finished, post actions queued, updating buttons.")
             QTimer.singleShot(0, self.update_button_states)


    # --- Parsing Slots (Unchanged) ---
    def parse_and_display_status(self, status_output):
        # (Keep exactly as before)
        self.clear_status_lists();staged,unstaged,untracked=[],[],[];#... rest unchanged ...
        lines=status_output.strip().split('\n');#... rest unchanged ...
        if staged:self.staged_list.addItems(sorted(staged));#... rest unchanged ...
        if unstaged:self.unstaged_list.addItems(sorted(unstaged));#... rest unchanged ...
        if untracked:self.untracked_list.addItems(sorted(untracked));#... rest unchanged ...

    def parse_and_display_history(self, log_output):
        # (Keep exactly as before)
        self.history_table.setRowCount(0);#... rest unchanged ...
        lines=log_output.strip().split('\n');#... rest unchanged ...
        self.history_table.setUpdatesEnabled(False);self.history_table.setSortingEnabled(False);#... rest unchanged ...
        rows=[];#... rest unchanged ...
        self.history_table.setRowCount(len(rows));#... rest unchanged ...
        self.history_table.setSortingEnabled(True);self.history_table.setUpdatesEnabled(True);#... rest unchanged ...


    # --- Specific Finished Slots (Now Removed) ---
    # REMOVE: on_refresh_finished, on_history_finished, on_staging_finished,
    # REMOVE: on_unstaging_finished, on_discard_finished, on_commit_finished
    # REMOVE: display_error


    # --- UI State & Helpers (clear*, update_button_states, set_ui_busy, closeEvent unchanged) ---
    def clear_status_lists(self): self.staged_list.clear();self.unstaged_list.clear();self.untracked_list.clear()
    def clear_history_view(self): self.history_table.setRowCount(0)
    def clear_commit_box(self): self.commit_message_box.clear()
    def clear_all_views(self): self.clear_status_lists();self.clear_history_view();self.clear_commit_box()
    def update_button_states(self):
        # (Keep exactly as before)
        repo_loaded=bool(self.repo_path);is_busy=self.current_git_thread and self.current_git_thread.isRunning();self.status_button.setEnabled(repo_loaded and not is_busy);self.refresh_history_button.setEnabled(repo_loaded and not is_busy);#... rest unchanged ...
    def set_ui_busy(self, busy):
        # (Keep exactly as before, maybe simplify flags later if needed)
        disabled=busy;self.open_button.setDisabled(disabled);self.status_button.setDisabled(disabled);self.refresh_history_button.setDisabled(disabled);self.stage_button.setDisabled(disabled);self.unstage_button.setDisabled(disabled);self.commit_button.setDisabled(disabled);self.commit_message_box.setReadOnly(disabled);#... rest unchanged ...
        if busy:QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:QApplication.restoreOverrideCursor();self.update_button_states() # Always update state when becoming not busy
    def closeEvent(self, event):
        # (Keep exactly as before)
        if self.current_git_thread and self.current_git_thread.isRunning():
            print("Waiting..."); self.setEnabled(False); wait_cursor=QApplication.overrideCursor(); QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); self.current_git_thread.wait(); QApplication.restoreOverrideCursor();
            if wait_cursor: QApplication.setOverrideCursor(wait_cursor)
            print("Finished. Closing."); event.accept()
        else: event.accept()
