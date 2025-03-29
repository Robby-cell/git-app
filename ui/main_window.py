import sys
import os
from typing import Optional

from PyQt6.QtWidgets import (QMainWindow, QTextEdit, QVBoxLayout, QSizePolicy,
                             QWidget, QPushButton, QFileDialog, QLabel,
                             QListWidget, QHBoxLayout, QSplitter, QFrame,
                             QApplication, QMenu, QMessageBox,
                             QTableWidget, QTableWidgetItem, # Ensure these are here
                             QTreeView, QInputDialog, QStackedWidget, QTextBrowser, QFormLayout
                             )
from PyQt6.QtCore import Qt, QPoint, QTimer, QModelIndex
from PyQt6.QtGui import QAction, QStandardItemModel, QStandardItem, QFont, QColor, QTextCharFormat

from .commit_graph_widget import CommitGraphWidget, ScrollableCommitGraphWidget

try:
    from git_ops.commands import GitCommandThread
    from utils.helpers import extract_file_path
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

GIT_LOG_FORMAT = "%H%x09%an%x09%ad%x09%s"
GIT_LOG_DATE_FORMAT = "iso"
MAX_LOG_COUNT = 200
DIFF_ADDED_COLOR = QColor("darkgreen")
DIFF_REMOVED_COLOR = QColor("darkred")
DIFF_HEADER_COLOR = QColor("darkblue")
DIFF_DEFAULT_COLOR = QColor("black")


class SimpleGitApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Simple Python Git GUI - Step 1: Commit Details") # Updated title
        self.setGeometry(50, 50, 1250, 800)
        self.repo_path = None; self.current_git_thread = None; self.current_operation_name = None; self._output_parser_slot = None; self._is_initial_load_status = False; self._is_initial_load_history = False; self._is_initial_load_branches = False; self.current_branch = None
        self.graph_widget_container: Optional[ScrollableCommitGraphWidget | QLabel] = None; self.graph_widget: Optional[CommitGraphWidget] = None
        self._selected_commit_hash_details: Optional[str] = None # Track hash being detailed

        self._init_ui() # Calls the updated UI setup below
        self._connect_signals()
        self.update_button_states()
        self._show_commit_detail_view(False) # Start with normal commit box visible

    def _init_ui(self):
        """Initialize UI elements."""
        self.central_widget = QWidget(); self.main_layout = QVBoxLayout(self.central_widget)

        # --- Top Bar ---
        self.top_bar_layout = QHBoxLayout(); self.open_button = QPushButton("Open Repository"); self.repo_label = QLabel("No repository opened."); self.repo_label.setWordWrap(True); self.fetch_button = QPushButton("Fetch"); self.fetch_button.setEnabled(False); self.pull_button = QPushButton("Pull"); self.pull_button.setEnabled(False); self.push_button = QPushButton("Push"); self.push_button.setEnabled(False); self.new_branch_button = QPushButton("New Branch..."); self.new_branch_button.setEnabled(False); self.refresh_branches_button = QPushButton("Refresh Branches"); self.refresh_branches_button.setEnabled(False); self.status_button = QPushButton("Refresh Status"); self.status_button.setEnabled(False); self.refresh_history_button = QPushButton("Refresh History"); self.refresh_history_button.setEnabled(False); self.top_bar_layout.addWidget(self.open_button); self.top_bar_layout.addWidget(self.repo_label, 1); self.top_bar_layout.addWidget(self.fetch_button); self.top_bar_layout.addWidget(self.pull_button); self.top_bar_layout.addWidget(self.push_button); self.top_bar_layout.addStretch(1); self.top_bar_layout.addWidget(self.new_branch_button); self.top_bar_layout.addStretch(1); self.top_bar_layout.addWidget(self.refresh_branches_button); self.top_bar_layout.addWidget(self.status_button); self.top_bar_layout.addWidget(self.refresh_history_button); self.main_layout.addLayout(self.top_bar_layout)

        # --- Top Level Splitter (Branches | Rest) ---
        self.top_splitter = QSplitter(Qt.Orientation.Horizontal)
        # --- Branches Panel (Left Side) ---
        self.branches_frame = QFrame(); self.branches_layout = QVBoxLayout(self.branches_frame); self.branches_layout.setContentsMargins(5, 5, 5, 5); self.branches_label = QLabel("Branches / Remotes"); self.branches_view = QTreeView(); self.branches_view.setHeaderHidden(True); self.branches_view.setEditTriggers(QTreeView.EditTrigger.NoEditTriggers); self.branches_model = QStandardItemModel(); self.branches_view.setModel(self.branches_model); self.branches_layout.addWidget(self.branches_label); self.branches_layout.addWidget(self.branches_view)

        # --- Main Area Container (Right Side) ---
        self.main_area_container = QWidget(); self.main_area_layout = QVBoxLayout(self.main_area_container); self.main_area_layout.setContentsMargins(0, 0, 0, 0)

        # --- Main Horizontal Splitter (Status+Diff | History Graph+Commit/Details) ---
        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)

        # --- Left side: Status+Diff ---
        self.status_diff_widget = QWidget(); self.status_diff_layout = QVBoxLayout(self.status_diff_widget); self.status_diff_layout.setContentsMargins(0,0,0,0); self.status_diff_splitter = QSplitter(Qt.Orientation.Vertical); self.status_frame = QFrame(); self.status_layout = QVBoxLayout(self.status_frame); self.status_layout.setContentsMargins(5, 5, 5, 5); self.staged_area_layout=QHBoxLayout();self.staged_label=QLabel("Staged Files:");self.unstage_button=QPushButton("Unstage Selected");self.unstage_button.setEnabled(False);self.staged_area_layout.addWidget(self.staged_label);self.staged_area_layout.addStretch();self.staged_area_layout.addWidget(self.unstage_button);self.staged_list=QListWidget();self.staged_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection); self.unstaged_area_layout=QHBoxLayout();self.unstaged_label=QLabel("Unstaged Changes:");self.stage_button=QPushButton("Stage Selected");self.stage_button.setEnabled(False);self.unstaged_area_layout.addWidget(self.unstaged_label);self.unstaged_area_layout.addStretch();self.unstaged_area_layout.addWidget(self.stage_button);self.unstaged_list=QListWidget();self.unstaged_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection);self.unstaged_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.untracked_label=QLabel("Untracked Files:");self.untracked_list=QListWidget();self.untracked_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection);self.untracked_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu); self.status_layout.addLayout(self.staged_area_layout);self.status_layout.addWidget(self.staged_list,1);self.status_layout.addLayout(self.unstaged_area_layout);self.status_layout.addWidget(self.unstaged_list,1);self.status_layout.addWidget(self.untracked_label);self.status_layout.addWidget(self.untracked_list,1);self.status_frame.setLayout(self.status_layout); self.diff_frame = QFrame(); self.diff_layout = QVBoxLayout(self.diff_frame); self.diff_layout.setContentsMargins(5, 5, 5, 5); self.diff_label = QLabel("Diff for selected file:"); self.diff_view = QTextEdit(); self.diff_view.setReadOnly(True); self.diff_view.setFontFamily("monospace"); self.diff_view.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap); self.diff_layout.addWidget(self.diff_label); self.diff_layout.addWidget(self.diff_view); self.status_diff_splitter.addWidget(self.status_frame); self.status_diff_splitter.addWidget(self.diff_frame); self.status_diff_splitter.setSizes([400, 250]); self.status_diff_layout.addWidget(self.status_diff_splitter)

        # --- Right side: History Graph + Commit Area / Details ---
        self.right_pane_widget=QWidget()
        self.right_pane_layout=QVBoxLayout(self.right_pane_widget)
        self.right_pane_layout.setContentsMargins(0,0,0,0)
        self.right_splitter=QSplitter(Qt.Orientation.Vertical)

        # -- History Graph (Top of Right Splitter) --
        if ScrollableCommitGraphWidget: self.graph_widget_container = ScrollableCommitGraphWidget(); self.graph_widget = self.graph_widget_container.graph_widget
        else: self.graph_widget_container = QLabel("Error: CommitGraphWidget failed to load."); self.graph_widget = None
        if self.graph_widget_container: self.graph_widget_container.setMinimumHeight(200); self.graph_widget_container.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # -- Bottom Area: Stacked Widget for Commit Box / Commit Details --
        self.bottom_right_stack = QStackedWidget()

        # -- Page 0: Standard Commit Area --
        self.commit_area_frame=QFrame(); self.commit_layout=QVBoxLayout(self.commit_area_frame); self.commit_layout.setContentsMargins(5,5,5,5); self.commit_label=QLabel("Commit Message:"); self.commit_message_box=QTextEdit(); self.commit_message_box.setPlaceholderText("Enter commit message here..."); self.commit_message_box.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding); self.commit_button=QPushButton("Commit Staged Changes"); self.commit_button.setEnabled(False); self.commit_layout.addWidget(self.commit_label); self.commit_layout.addWidget(self.commit_message_box,1); self.commit_layout.addWidget(self.commit_button); self.commit_area_frame.setMinimumHeight(100); self.commit_area_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.bottom_right_stack.addWidget(self.commit_area_frame)

        # -- Page 1: Commit Details Area --
        self.commit_detail_widget = QWidget()
        self.commit_detail_layout = QVBoxLayout(self.commit_detail_widget)
        self.commit_detail_layout.setContentsMargins(5, 5, 5, 5)
        # Metadata Form
        self.detail_form_layout = QFormLayout()
        self.detail_hash_label = QLabel("Commit:")
        self.detail_hash_value = QLabel() # Use QLabel for read-only hash
        self.detail_hash_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_author_label = QLabel("Author:")
        self.detail_author_value = QLabel()
        self.detail_author_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_date_label = QLabel("Date:")
        self.detail_date_value = QLabel()
        self.detail_date_value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.detail_form_layout.addRow(self.detail_hash_label, self.detail_hash_value)
        self.detail_form_layout.addRow(self.detail_author_label, self.detail_author_value)
        self.detail_form_layout.addRow(self.detail_date_label, self.detail_date_value)

        # Commit Message View
        self.detail_message_label = QLabel("Message:")
        self.detail_message_view = QTextBrowser() # Good for read-only, links etc.
        self.detail_message_view.setOpenExternalLinks(True)
        self.detail_message_view.setMinimumHeight(60)
        self.detail_message_view.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)

        # Changed Files List
        self.detail_files_label = QLabel("Changed Files:")
        self.detail_files_list = QListWidget()
        self.detail_files_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        self.detail_files_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Adding to UI
        self.commit_detail_layout.addLayout(self.detail_form_layout)
        self.commit_detail_layout.addWidget(self.detail_message_label)
        self.commit_detail_layout.addWidget(self.detail_message_view)
        self.commit_detail_layout.addWidget(self.detail_files_label)
        self.commit_detail_layout.addWidget(self.detail_files_list, 1) # Give list stretch factor

        self.bottom_right_stack.addWidget(self.commit_detail_widget)

        # Add History Graph Container and Bottom Stack to the right splitter
        if self.graph_widget_container: self.right_splitter.addWidget(self.graph_widget_container)
        self.right_splitter.addWidget(self.bottom_right_stack) # <<< Add Stack instead of commit_area_frame
        self.right_splitter.setSizes([450, 150])

        self.right_pane_layout.addWidget(self.right_splitter)

        # --- Assemble Splitters ---
        self.main_splitter.addWidget(self.status_diff_widget)
        self.main_splitter.addWidget(self.right_pane_widget)
        self.main_splitter.setSizes([550, 550])
        self.main_area_layout.addWidget(self.main_splitter)
        self.top_splitter.addWidget(self.branches_frame)
        self.top_splitter.addWidget(self.main_area_container)
        self.top_splitter.setSizes([200, 1050])
        self.main_layout.addWidget(self.top_splitter, 1)

        # --- Error/Output Area ---
        self.error_output_area = QTextEdit(); self.error_output_area.setReadOnly(True); self.error_output_area.setMaximumHeight(60); self.main_layout.addWidget(self.error_output_area)
        self.setCentralWidget(self.central_widget)

    def _connect_signals(self):
        """Connect signals to slots."""
        # --- Top Bar Actions ---
        self.open_button.clicked.connect(self.open_repository)
        self.status_button.clicked.connect(self.refresh_status)
        self.refresh_history_button.clicked.connect(self.refresh_history)
        self.refresh_branches_button.clicked.connect(self.refresh_branches)
        self.new_branch_button.clicked.connect(self.create_new_branch)
        self.fetch_button.clicked.connect(self.fetch_all)
        self.pull_button.clicked.connect(self.pull_current_branch)
        self.push_button.clicked.connect(self.push_current_branch)

        # --- State Update Triggers ---
        # Update button enable state when list selections change
        self.staged_list.itemSelectionChanged.connect(self.update_button_states)
        self.unstaged_list.itemSelectionChanged.connect(self.update_button_states)
        self.untracked_list.itemSelectionChanged.connect(self.update_button_states)
        # Update commit button enable state when staged list content changes
        self.staged_list.model().rowsInserted.connect(self.update_button_states)
        self.staged_list.model().rowsRemoved.connect(self.update_button_states)
        # Update commit button enable state when commit message changes
        self.commit_message_box.textChanged.connect(self.update_button_states)

        # --- Staging Area Action Buttons ---
        self.stage_button.clicked.connect(self.stage_selected_files)
        self.unstage_button.clicked.connect(self.unstage_selected_files)
        self.commit_button.clicked.connect(self.commit_changes)

        # --- Context Menus (Status Lists) ---
        self.unstaged_list.customContextMenuRequested.connect(self.show_status_context_menu)
        self.untracked_list.customContextMenuRequested.connect(self.show_status_context_menu)

        # --- Branch View Actions ---
        self.branches_view.doubleClicked.connect(self.on_branch_double_clicked) # For checkout

        # --- Commit History / Details Connections ---
        # Connect graph widget's selection signal to show details
        if self.graph_widget: # Check if graph widget was initialized
            self.graph_widget.commit_selected.connect(self.show_commit_details)
        else:
            print("Warning: Graph widget not available for signal connection.")
        # Connect selection in commit detail's changed files list to show diff for that file
        self.detail_files_list.currentItemChanged.connect(self.show_commit_file_diff)
        # Clear diff view when selection is lost in detail files list
        self.detail_files_list.itemSelectionChanged.connect(
            lambda: self.clear_diff_view() if not self.detail_files_list.currentItem() else None
        )


        # --- Diff View Connections (Working Tree / Index) ---
        # Show diff when item selection changes in status lists
        self.staged_list.currentItemChanged.connect(self.show_diff)
        self.unstaged_list.currentItemChanged.connect(self.show_diff)
        # Clear diff view when selection is lost in status lists
        self.staged_list.itemSelectionChanged.connect(
            lambda: self.clear_diff_view() if not self.staged_list.currentItem() else None
        )
        self.unstaged_list.itemSelectionChanged.connect(
            lambda: self.clear_diff_view() if not self.unstaged_list.currentItem() else None
        )
        # Clear diff view if an untracked file is selected
        self.untracked_list.itemSelectionChanged.connect(
            lambda: self.clear_diff_view() if self.untracked_list.selectedItems() else None
        )

    def _show_commit_detail_view(self, show_details: bool):
        """Switches the bottom right pane between commit box and detail view."""
        if not self.bottom_right_stack: # Safety check
             print("Error: Bottom right stack widget not initialized.")
             return

        if show_details:
            self.bottom_right_stack.setCurrentWidget(self.commit_detail_widget)
        else:
            # Clear details when switching away
            if self._selected_commit_hash_details: # Only clear if details were shown
                 self.detail_hash_value.clear()
                 self.detail_author_value.clear()
                 self.detail_date_value.clear()
                 self.detail_message_view.clear()
                 self.detail_files_list.clear()
                 self.clear_diff_view() # Clear diff associated with commit details
                 self._selected_commit_hash_details = None # Clear the stored hash
            # Deselect graph node visually?
            if self.graph_widget and self.graph_widget._selected_commit_hash:
                 self.graph_widget._selected_commit_hash = None
                 self.graph_widget.update()

            self.bottom_right_stack.setCurrentWidget(self.commit_area_frame)
            self.update_button_states() # Ensure commit button state is correct

    def show_commit_details(self, commit_hash: str):
        """Fetches and displays details for the selected commit hash."""
        if not commit_hash or not self.repo_path:
            self._show_commit_detail_view(False) # Revert to commit box if invalid hash/repo
            return

        # Prevent re-fetching if the same commit is already selected and detailed
        if commit_hash == self._selected_commit_hash_details:
             print(f"Commit {commit_hash[:7]} details already shown.")
             self._show_commit_detail_view(True) # Ensure detail view is visible
             return

        # Check if busy *before* proceeding
        if not self._can_run_git_command(f"show commit {commit_hash[:7]}"):
            # Don't switch view if busy, maybe provide feedback?
            self.error_output_area.setText(f"Cannot show details: {self.current_operation_name} is running.")
            # Deselect node visually? (Requires graph widget modification)
            # if self.graph_widget: self.graph_widget.select_commit(None)
            return

        print(f"Fetching details for commit: {commit_hash}")
        self._selected_commit_hash_details = commit_hash # Store hash being detailed *before* starting command
        self._show_commit_detail_view(True) # Switch to detail view

        # Clear previous details immediately and show placeholder
        self.detail_hash_value.setText(f"{commit_hash[:12]}...")
        self.detail_author_value.clear()
        self.detail_date_value.clear()
        self.detail_message_view.setText("Loading details...")
        self.detail_files_list.clear()
        self.clear_diff_view() # Clear diff associated with previous selection

        self.error_output_area.setText(f"Loading details for {commit_hash[:7]}...")
        self.set_ui_busy(True) # Set busy while fetching details

        # Command to get metadata and file status changes
        # Use null separators for metadata, then rely on --stat format after null
        git_show_format = "%H%x00%an%x00%ae%x00%aD%x00%cn%x00%ce%x00%cD%x00%B%x00" # Note trailing null
        command = ['git', 'show', f'--pretty=format:{git_show_format}', '--stat=4096', '--no-patch', commit_hash] # Get stat, no diff yet

        # Use the new parser slot for commit details
        self._start_git_thread(command, "Show Commit", parser_slot=self._parse_and_display_commit_details)

    def _parse_and_display_commit_details(self, show_output: str):
        """Parses the output of 'git show --pretty=format --stat' and updates the detail view."""
        print("Parsing commit details...")
        # Clear previous details first
        self.detail_hash_value.clear()
        self.detail_author_value.clear()
        self.detail_date_value.clear()
        self.detail_message_view.clear()
        self.detail_files_list.clear()

        try:
            # --- Parse Metadata (separated by null bytes) ---
            metadata_part, stat_part = show_output.split('\x00\n', 1) # Split metadata from stat part
            metadata = metadata_part.split('\x00')
            if len(metadata) < 8:
                print(f"Warning: Could not parse commit metadata fully. Parts: {len(metadata)}")
                self.detail_message_view.setText("Error parsing commit metadata.")
                return

            commit_hash = metadata[0]
            author_name = metadata[1]
            author_email = metadata[2]
            author_date = metadata[3]
            # committer_name = metadata[4] # Not displayed currently
            # committer_email = metadata[5] # Not displayed currently
            # commit_date = metadata[6] # Not displayed currently
            commit_body = metadata[7] # The rest is the body

            # --- Populate Metadata UI ---
            self.detail_hash_value.setText(commit_hash)
            # Maybe format author/date nicely
            self.detail_author_value.setText(f"{author_name} <{author_email}>")
            self.detail_date_value.setText(author_date) # Use the formatted date from git
            self.detail_message_view.setText(commit_body.strip()) # Display full message

            # --- Parse File Statistics (`--stat` output) ---
            # Example stat line: " path/to/file.txt | 10 +++++-----"
            # Example rename: " path/{old => new}.txt | Bin 0 -> 1024 bytes" (Handle binary later)
            file_changes = []
            # Split stat part carefully, handling potential empty lines
            stat_lines = [line.strip() for line in stat_part.strip().split('\n') if line.strip()]

            # The last line of --stat is often a summary line, ignore it for file list
            summary_line_index = -1
            for i, line in reversed(list(enumerate(stat_lines))):
                if "file changed" in line or "files changed" in line:
                     summary_line_index = i
                     break

            if summary_line_index != -1:
                 stat_lines = stat_lines[:summary_line_index] # Exclude summary line

            for line in stat_lines:
                parts = line.split('|', 1)
                if len(parts) == 2:
                    file_path = parts[0].strip()
                    # Basic handling for rename syntax like " dir/{a.txt => b.txt}"
                    if '{' in file_path and '=>' in file_path and '}' in file_path:
                         # Extract the 'new' path part for simplicity
                         prefix = file_path[:file_path.find('{')]
                         suffix_part = file_path[file_path.find('=>')+2:file_path.find('}')]
                         file_path = prefix + suffix_part

                    # Could add change summary (+/-) as tooltip later
                    # change_summary = parts[1].strip()
                    file_changes.append(file_path)

            # --- Populate File List ---
            if file_changes:
                self.detail_files_list.addItems(sorted(file_changes))
            else:
                self.detail_files_list.addItem("No file changes in this commit.") # Or leave empty

            print("Commit details parsed successfully.")

        except Exception as e:
            print(f"Error parsing 'git show' output: {e}\nOutput was:\n{show_output[:500]}...") # Log error and partial output
            self.detail_message_view.setText(f"Error displaying commit details.\n{e}")
            # Reset stored hash if parsing failed badly?
            # self._selected_commit_hash_details = None

    def show_commit_file_diff(self):
        """Shows the diff for a file selected in the commit details file list."""
        current_item = self.detail_files_list.currentItem()
        # Use the hash stored when the commit detail view was populated
        commit_hash = self._selected_commit_hash_details

        if not current_item or not commit_hash or not self.repo_path:
            # Don't clear diff here, maybe user wants to see previous diff
            # self.clear_diff_view()
            return

        # Assume item text is the file path (already processed potential renames)
        file_path = current_item.text().strip()
        if not file_path:
            self.clear_diff_view()
            return

        # Don't run if busy
        if not self._can_run_git_command(f"show diff for {file_path} in {commit_hash[:7]}"):
            return

        self.diff_view.setText(f"Loading diff for {file_path} in commit {commit_hash[:7]}...")
        self.diff_label.setText(f"Changes to {file_path} in {commit_hash[:7]}:")

        # Command to show diff for a specific file within a commit vs its first parent
        # Use hash^! syntax for merges? No, diff vs first parent is more typical for browsing.
        # Use `git diff <parent> <commit> -- <file>` for robustness against octopus merges?
        # Simpler: diff commit vs its immediate predecessor `hash^..hash`
        # Note: This will fail for the initial commit (no parents). Handle this?
        # Check if commit has parents? `git rev-list --parents -n 1 <hash>`
        # Alternative: `git show <hash> -- <file>` (includes diff in output, needs parsing)

        # Let's use `git diff <hash>^ <hash> -- <file>` (diff against first parent)
        # This needs error handling if it's the root commit.
        # Simpler robust option: `git diff-tree --no-commit-id --patch -r <hash>^ <hash> -- <file>`
        # Safest might be `git show <hash> -- <file>` and parse the diff section.

        # Using `git diff <hash>^.. <hash>` for now, assuming non-root commit primarily
        # We will rely on git failing gracefully for the root commit for now.
        command = ['git', 'diff', f"{commit_hash}^..{commit_hash}", '--', file_path]

        # Point parser to the existing diff display function
        self._start_git_thread(command, "Commit Diff", parser_slot=self._display_diff)

    # --- Context Menu Slot ---
    def show_status_context_menu(self, point: QPoint):
        # (Unchanged from Step 10)
        source_list = self.sender()
        menu = QMenu(self)
        if isinstance(source_list, QListWidget):
            selected_items = source_list.selectedItems()
            if selected_items:
                action_text = ""
                if source_list is self.unstaged_list:
                    action_text = "Discard Changes..."
                elif source_list is self.untracked_list:
                    action_text = "Delete Untracked Files..."
                if action_text:
                    discard_action = QAction(action_text, self)
                    discard_action.triggered.connect(
                        lambda: self.discard_selected_files(source_list)
                    )
                    menu.addAction(discard_action)
        if not menu.isEmpty():
            menu.exec(source_list.mapToGlobal(point))

    # --- Action Slots ---

    def open_repository(self):
        # (Unchanged from Step 10 - starts refresh chain)
        if self.current_git_thread:
            return
        path = QFileDialog.getExistingDirectory(self, "Select Git Repository")
        if path:
            git_dir = os.path.join(path, ".git")
            if os.path.isdir(git_dir) or os.path.isfile(git_dir):
                self.repo_path = path
                self.repo_label.setText(f"Repository: {self.repo_path}")
                self.status_button.setEnabled(True)
                self.refresh_history_button.setEnabled(True)
                self.refresh_branches_button.setEnabled(True)
                self.new_branch_button.setEnabled(True)
                self.fetch_button.setEnabled(True)  # Enable Fetch
                self.clear_all_views()
                self.error_output_area.clear()
                self._is_initial_load_branches = True
                self._is_initial_load_status = True
                self._is_initial_load_history = True
                self.refresh_branches()  # Start chain
            else:  # Invalid path
                self.repo_path = None
                self.repo_label.setText("Not a valid Git repository.")
                self.status_button.setEnabled(False)
                self.refresh_history_button.setEnabled(False)
                self.refresh_branches_button.setEnabled(False)
                self.new_branch_button.setEnabled(False)
                self.fetch_button.setEnabled(False)
                self.clear_all_views()
                self.update_button_states()
                self.error_output_area.setText(
                    "Selected directory is not a Git repository."
                )
    
    def pull_current_branch(self):
        """Runs 'git pull' for the current branch."""
        if not self.current_branch:
            self.error_output_area.setText("Cannot pull: No local branch checked out?")
            return
        if not self._can_run_git_command("pull"): return

        self.error_output_area.setText(f"Pulling changes for branch '{self.current_branch}'...")
        self.set_ui_busy(True)
        # Assume remote 'origin' for simplicity
        # TODO: Add logic to determine correct remote and upstream branch
        #       Maybe query git config branch.<name>.remote and branch.<name>.merge?
        command = ['git', 'pull', 'origin', self.current_branch]
        self._start_git_thread(command, "Pull")

    def push_current_branch(self):
        """Runs 'git push' for the current branch."""
        if not self.current_branch:
            self.error_output_area.setText("Cannot push: No local branch checked out?")
            return
        if not self._can_run_git_command("push"): return

        self.error_output_area.setText(f"Pushing branch '{self.current_branch}'...")
        self.set_ui_busy(True)
        # Assume remote 'origin' and push the current branch to its counterpart
        # TODO: Add logic for setting upstream (-u), force push option?
        # TODO: Query upstream using `git rev-parse --abbrev-ref @{u}`? Handle no upstream.
        command = ['git', 'push', 'origin', self.current_branch]
        self._start_git_thread(command, "Push")

    def refresh_status(self):
        # (Unchanged)
        if not self._can_run_git_command("refresh status"):
            return
        self.clear_status_lists()
        self.clear_diff_view()
        self.error_output_area.setText("Refreshing status...")
        self.set_ui_busy(True)
        self._start_git_thread(
            ["git", "status", "--porcelain=v1", "--untracked-files=normal"],
            "Status",
            parser_slot=self._parse_and_display_status,
        )

    def refresh_history(self):
        """Runs 'git log' for graph and updates the graph widget."""
        if not self._can_run_git_command("refresh history"): return
        # Check if the graph widget exists before proceeding
        if not self.graph_widget:
            self.error_output_area.setText("History graph widget is not available.")
            return

        self.clear_history_view() # Clear graph data immediately
        self.error_output_area.setText("Refreshing history graph...")
        self.set_ui_busy(True)

        # Use format string including Parent hashes (%P) and raw date for sorting
        # Use null character \x00 as separator
        git_graph_log_format = "%H%x00%P%x00%an%x00%ad%x00%s"
        command = [
            'git', 'log',
            f'--pretty=format:{git_graph_log_format}', # <<< Use new format
            f'--date=raw', # Use raw timestamp (seconds + timezone)
            f'--max-count={MAX_LOG_COUNT}', # Limit for performance
            'HEAD' # Log current branch by default
            # Consider adding '--all --branches' later to show more complex history
        ]
        # Point to the new graph parser
        self._start_git_thread(command, "History", parser_slot=self._parse_and_update_graph)

    def _parse_and_update_graph(self, log_output):
        """Parses git log output (with parents) and updates the graph widget."""
        # Check if graph widget exists (might fail during init)
        if not self.graph_widget:
            print("Error: Graph widget not initialized, cannot parse history.")
            return

        print("Parsing commit data for graph...")
        commits_data = []
        separator = '\x00' # Null character used in format string
        lines = log_output.strip().split('\n')

        if not log_output.strip():
            print("History is empty or git log output was empty.")
            self.graph_widget.setData([]) # Ensure graph is cleared
            return

        for line in lines:
            if not line: continue
            parts = line.split(separator, 4) # Hash, Parents, Author, Date(ts+tz), Subject
            if len(parts) == 5:
                commit_hash = parts[0]
                parent_hashes = parts[1].split() # Parents are space-separated
                author = parts[2]
                try:
                    # Date is raw timestamp + timezone offset (e.g., "1678886400 -0700")
                    # We mainly need the timestamp for sorting.
                    date_ts = int(parts[3].split()[0])
                except (ValueError, IndexError):
                    print(f"Warning: Could not parse date timestamp from: {parts[3]}")
                    date_ts = 0 # Fallback timestamp
                subject = parts[4]

                commits_data.append({
                    "hash": commit_hash,
                    "parents": parent_hashes,
                    "author": author,
                    "date_ts": date_ts, # Store timestamp for sorting
                    "msg": subject # Simplified message for now
                    # Could add full date string later if needed for display
                })
            else:
                 print(f"Warning: Could not parse graph log line (expected 5 parts, got {len(parts)}): {line}")

        if commits_data:
            print(f"Updating graph with {len(commits_data)} commits.")
            # Pass the parsed data to the graph widget
            self.graph_widget.setData(commits_data)
        else:
            print("No valid graph log entries parsed.")
            self.graph_widget.setData([]) # Ensure graph is cleared if parsing fails

    def refresh_branches(self):
        # (Unchanged)
        if not self._can_run_git_command("refresh branches"):
            return
        self.clear_branches_view()
        self.error_output_area.setText("Refreshing branches...")
        self.set_ui_busy(True)
        self._start_git_thread(
            [
                "git",
                "for-each-ref",
                "--format=%(HEAD)%(refname)",
                "refs/heads",
                "refs/remotes",
            ],
            "Branches",
            parser_slot=self._parse_and_display_branches,
        )

    def create_new_branch(self):
        # (Unchanged)
        if not self._can_run_git_command("create branch"):
            return
        branch_name, ok = QInputDialog.getText(
            self, "Create New Branch", "Enter new branch name:"
        )
        if ok and branch_name:
            branch_name = branch_name.strip().replace(" ", "_")
            if not branch_name:
                self.error_output_area.setText("Branch name cannot be empty.")
                return
            self.error_output_area.setText(f"Creating branch '{branch_name}'...")
            self.set_ui_busy(True)
            self._start_git_thread(["git", "branch", branch_name], "Create Branch")
        else:
            self.error_output_area.setText("Branch creation cancelled.")

    def checkout_branch(self, branch_name):
        # (Unchanged)
        if not branch_name:
            return
        if branch_name == self.current_branch:
            self.error_output_area.setText(f"Already on branch '{branch_name}'.")
            return
        if not self._can_run_git_command(f"checkout branch '{branch_name}'"):
            return
        self.error_output_area.setText(f"Checking out branch '{branch_name}'...")
        self.set_ui_busy(True)
        self._start_git_thread(["git", "checkout", branch_name], "Checkout")

    def on_branch_double_clicked(self, index: QModelIndex):
        # (Unchanged)
        item = self.branches_model.itemFromIndex(index)
        parent = item.parent() if item else None
        if item and parent and parent.text() == "Local":
            branch_name = item.data(Qt.ItemDataRole.UserRole)
            if branch_name:
                self.checkout_branch(branch_name)
        elif item:
            self.error_output_area.setText(
                "Can only check out local branches via double-click."
            )

    def show_diff(self):
        """Shows git diff for the currently selected file in STAGED or UNSTAGED lists."""
        source_list = None
        selected_item = None
        is_staged = False
        is_working_tree_diff = False # Flag to distinguish from commit diff

        # Prioritize selection in status lists
        if self.unstaged_list.currentItem() and self.unstaged_list.currentItem().isSelected():
            source_list = self.unstaged_list
            selected_item = source_list.currentItem()
            is_staged = False
            is_working_tree_diff = True
        elif self.staged_list.currentItem() and self.staged_list.currentItem().isSelected():
            source_list = self.staged_list
            selected_item = source_list.currentItem()
            is_staged = True
            is_working_tree_diff = True

        # If the active selection source was the working tree lists...
        if is_working_tree_diff:
            # Ensure detail file list selection doesn't interfere / clear it?
            # self.detail_files_list.clearSelection() # Optional: enforce single focus

            if not selected_item or not self.repo_path:
                 self.clear_diff_view(); return

            file_path = extract_file_path(selected_item.text())
            if not file_path:
                 self.clear_diff_view(); return

            if not self._can_run_git_command("show working tree diff"): return

            diff_type = "Staged" if is_staged else "Unstaged"
            self.diff_view.setText(f"Loading {diff_type} diff for {file_path}...")
            self.diff_label.setText(f"{diff_type} Changes to {file_path}:")

            command = ['git', 'diff']
            if is_staged: command.append('--cached')
            command.extend(['--', file_path])

            self._start_git_thread(command, "Working Tree Diff", parser_slot=self._display_diff)

        # If no selection in status lists, don't clear diff unless explicitly needed
        # (e.g., if selection is lost in detail list, handled by its itemSelectionChanged)
        # else:
        #    # Consider if clearing is desired when *nothing* is selected anywhere
        #    # self.clear_diff_view()
        #    pass

    def stage_selected_files(self):
        """Runs 'git add' on selected files in the unstaged AND untracked lists."""
        # <<< Get selections from BOTH lists >>>
        selected_unstaged_items = self.unstaged_list.selectedItems()
        selected_untracked_items = self.untracked_list.selectedItems()

        # Combine items from both lists
        all_selected_items = selected_unstaged_items + selected_untracked_items

        if not all_selected_items:
             self.error_output_area.setText("No unstaged or untracked files selected.")
             return # Exit if nothing is selected in either list

        if not self._can_run_git_command("stage files"): return

        # Extract unique file paths from all selected items
        # Use a set to automatically handle duplicates if a file is somehow selected in both (unlikely)
        files_to_stage_set = set()
        for item in all_selected_items:
            path = extract_file_path(item.text())
            if path: # Ensure path extraction was successful
                files_to_stage_set.add(path)

        files_to_stage = list(files_to_stage_set) # Convert back to list for command

        if not files_to_stage:
            self.error_output_area.setText("Could not determine files to stage.")
            return # Exit if path extraction failed for all items

        # Proceed with git add command
        self.error_output_area.setText(f"Staging {len(files_to_stage)} file(s)...")
        self.set_ui_busy(True)
        # Use '--' to handle filenames starting with '-'
        command = ['git', 'add', '--'] + files_to_stage
        self._start_git_thread(command, "Stage") # Central handler takes care of refresh

    def unstage_selected_files(self):
        # (Unchanged)
        selected_items = self.staged_list.selectedItems()
        if not selected_items or not self._can_run_git_command("unstage files"):
            return
        files = [extract_file_path(item.text()) for item in selected_items]
        if not files:
            return
        self.error_output_area.setText(f"Unstaging {len(files)} file(s)...")
        self.set_ui_busy(True)
        self._start_git_thread(["git", "reset", "HEAD", "--"] + files, "Unstage")

    def discard_selected_files(self, source_list):
        # (Unchanged)
        selected_items = source_list.selectedItems()
        if not selected_items or not self._can_run_git_command("discard changes/files"):
            return
        files = [extract_file_path(item.text()) for item in selected_items]
        if not files:
            return
        num_files, file_plural = len(files), "file" if len(files) == 1 else "files"
        list_sample = (
            f"{files[0]}{f' and {num_files - 1} other(s)' if num_files > 1 else ''}"
        )
        if source_list is self.unstaged_list:
            confirm_title, confirm_text, command_base, action_name = (
                "Confirm Discard Changes",
                f"Discard changes to {num_files} {file_plural}?\n({list_sample})",
                ["git", "checkout", "HEAD", "--"],
                "Discard",
            )
        elif source_list is self.untracked_list:
            confirm_title, confirm_text, command_base, action_name = (
                "Confirm Delete Untracked Files",
                f"PERMANENTLY DELETE {num_files} untracked {file_plural}?\n({list_sample})",
                ["git", "clean", "-fdx", "--"],
                "Clean",
            )
        else:
            return
        reply = QMessageBox.warning(
            self,
            confirm_title,
            confirm_text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if reply != QMessageBox.StandardButton.Yes:
            self.error_output_area.setText(f"{action_name} operation cancelled.")
            return
        self.error_output_area.setText(f"{action_name}ing files...")
        self.set_ui_busy(True)
        self._start_git_thread(command_base + files, action_name)

    def commit_changes(self):
        # (Unchanged)
        if not self._can_run_git_command("commit"):
            return
        if self.staged_list.count() == 0:
            self.error_output_area.setText("Cannot commit: No files staged.")
            return
        commit_message = self.commit_message_box.toPlainText().strip()
        if not commit_message:
            self.error_output_area.setText(
                "Cannot commit: Commit message cannot be empty."
            )
            self.commit_message_box.setFocus()
            return
        self.error_output_area.setText("Committing staged changes...")
        self.set_ui_busy(True)
        self._start_git_thread(["git", "commit", "-m", commit_message], "Commit")

    def fetch_all(self):  # <<< NEW METHOD
        """Runs 'git fetch --all --prune'."""
        if not self._can_run_git_command("fetch"):
            return

        self.error_output_area.setText("Fetching all remotes...")
        self.set_ui_busy(True)
        # Use --prune to remove deleted remote branches
        command = ["git", "fetch", "--all", "--prune"]
        self._start_git_thread(
            command, "Fetch"
        )  # Output can be noisy, don't parse for now

    # --- Git Command Handling ---

    def _can_run_git_command(self, operation_name="perform Git operation"):
        # (Unchanged)
        if not self.repo_path:
            self.error_output_area.setText("No repository open.")
            return False
        if self.current_git_thread and self.current_git_thread.isRunning():
            running_op = self.current_operation_name or "a Git command"
            self.error_output_area.setText(
                f"Cannot {operation_name}: {running_op} is already running."
            )
            return False
        return True

    def _start_git_thread(self, command, operation_name, parser_slot=None):
        # (Unchanged)
        try:
            self.current_operation_name = operation_name
            self._output_parser_slot = parser_slot
            thread = GitCommandThread(command, self.repo_path)
            if self.current_git_thread:
                try:
                    self.current_git_thread.command_finished.disconnect(
                        self._on_git_command_finished
                    )
                except TypeError:
                    pass
            thread.command_finished.connect(self._on_git_command_finished)
            self.current_git_thread = thread
            self.current_git_thread.start()
        except Exception as e:
            self.error_output_area.setText(
                f"Failed to start Git thread for {operation_name}: {e}"
            )
            self.current_operation_name = None
            self.current_git_thread = None
            self._output_parser_slot = None
            self.set_ui_busy(False)

    # --- Central Finished Slot ---

    def _on_git_command_finished(self, finished_thread, success, stdout, stderr):
        """Central handler for when any GitCommandThread finishes."""
        if finished_thread != self.current_git_thread:
            print(f"Ignoring finished signal from unexpected thread: {finished_thread}")
            return

        op_name = self.current_operation_name; parser = self._output_parser_slot
        initial_load_branches = self._is_initial_load_branches and op_name == "Branches"
        initial_load_status = self._is_initial_load_status and op_name == "Status"
        initial_load_history = self._is_initial_load_history and op_name == "History"

        print(f"Git command finished: {op_name}, Success: {success}")

        self.current_git_thread = None; self.current_operation_name = None; self._output_parser_slot = None
        if initial_load_branches: self._is_initial_load_branches = False
        if initial_load_status: self._is_initial_load_status = False
        if initial_load_history: self._is_initial_load_history = False

        error_occurred = not success
        post_action_refresh_status = False; post_action_refresh_history = False; post_action_refresh_branches = False

        if success:
            if parser:
                try: parser(stdout)
                except Exception as e: self.error_output_area.setText(f"Error processing output for {op_name}: {e}"); print(f"Parser Error ({op_name}): {e}"); error_occurred = True
            elif op_name in ["Fetch", "Pull", "Push", "Show Commit", "Commit Diff", "Working Tree Diff"]: # Added Show/Diff ops
                 # Clear specific 'Running...' messages if no parser handled output
                 if f"{op_name}..." in self.error_output_area.toPlainText() or f"{op_name}ing..." in self.error_output_area.toPlainText():
                      self.error_output_area.clear()
                 # Show simple success for remote ops if stdout was empty
                 elif not stdout.strip() and op_name in ["Fetch", "Pull", "Push"]:
                      self.error_output_area.setText(f"{op_name} successful (no output).")
                 # Don't show generic success for Show/Diff ops, lack of error is enough

            # --- Determine Follow-Up Actions on Success ---
            if op_name in ["Commit", "Checkout", "Pull", "Push", "Fetch"]:
                post_action_refresh_status = True; post_action_refresh_history = True; post_action_refresh_branches = True
                if op_name == "Commit": self.commit_message_box.clear()
                if op_name == "Checkout": self._show_commit_detail_view(False); self._selected_commit_hash_details = None # Revert to commit box after checkout
            elif op_name == "Create Branch":
                 post_action_refresh_branches = True
            elif op_name == "Branches" and initial_load_branches: post_action_refresh_status = True
            elif op_name == "Status" and initial_load_status: post_action_refresh_history = True
            elif op_name in ["Stage", "Unstage", "Discard", "Clean"]: post_action_refresh_status = True
            elif op_name in ["Diff", "Show Commit", "Commit Diff", "Working Tree Diff"]: pass # No automatic refreshes needed

            if op_name == "Status": # Update clean message
                 is_clean = (self.staged_list.count()==0 and self.unstaged_list.count()==0 and self.untracked_list.count()==0)
                 if is_clean: self.error_output_area.setText("Working tree clean.")

        else: # Handle Failure
            error_message = ""
            # --- Specific Error Handling ---
            if op_name == "Checkout" and "overwritten by checkout" in stderr: error_message = f"Checkout failed: Commit or stash changes first.\nDetails:\n{stderr.strip()}"
            elif op_name == "Pull" and "Merge conflict" in stderr: error_message = f"Pull failed: Merge conflicts detected. Resolve manually and commit.\nDetails:\n{stderr.strip()}"; post_action_refresh_status = True # Refresh status to show conflicts
            elif op_name == "Pull" and "overwritten by merge" in stderr: error_message = f"Pull failed: Local changes would be overwritten. Commit or stash first.\nDetails:\n{stderr.strip()}"
            elif op_name == "Push" and "rejected" in stderr: error_message = f"Push rejected. Remote has new commits (pull first)?\nDetails:\n{stderr.strip()}"
            elif op_name in ["Fetch", "Pull", "Push"] and ("Authentication failed" in stderr or "could not read Username" in stderr or "Permission denied" in stderr or "Repository not found" in stderr): error_message = f"{op_name} failed: Authentication/permission issue. Check credentials/keys/URL.\nDetails:\n{stderr.strip()}"
            elif op_name == "Commit Diff" and "unknown revision or path not in the working tree" in stderr: # Handle diffing root commit parent
                 error_message = f"Cannot diff initial commit (no parent)."
                 self.clear_diff_view() # Clear the diff view specifically
            # --- Generic Error ---
            else:
                 error_message = f"Error during {op_name}:\n{stderr.strip()}"
                 if not stderr.strip() and stdout.strip(): error_message += f"\nOutput:\n{stdout.strip()}"

            self.error_output_area.setText(error_message)
            # Clear relevant views on error
            if op_name == "Diff" or op_name == "Commit Diff" or op_name == "Working Tree Diff": self.clear_diff_view()
            if op_name == "History": self.clear_history_view()
            if op_name == "Show Commit": # Clear detail view and revert stack on error
                self._show_commit_detail_view(False)
                self._selected_commit_hash_details = None


        # --- Trigger Post Actions using QTimer ---
        delay = 10
        if post_action_refresh_branches: QTimer.singleShot(delay, self.refresh_branches); delay += 20
        if post_action_refresh_status: QTimer.singleShot(delay, self.refresh_status); delay += 20
        if post_action_refresh_history: QTimer.singleShot(delay, self.refresh_history); delay += 20


        # --- Update UI Busy State ---
        # Unlock UI only if no further actions are queued
        if not post_action_refresh_status and not post_action_refresh_history and not post_action_refresh_branches:
             # Use QTimer to ensure unlock happens after potential signal processing
             QTimer.singleShot(0, lambda: self.set_ui_busy(False))
        else:
             # If actions are queued, just update button states for now
             QTimer.singleShot(0, self.update_button_states)

    # --- Parsing / Display Slots ---

    def _parse_and_display_status(self, status_output):
        # (Unchanged)
        self.clear_status_lists()
        staged, unstaged, untracked = [], [], []
        lines = status_output.strip().split("\n")
        for line in lines:  # ... (rest of parsing logic) ...
            if not line:
                continue
            xy_status = line[:2]
            path = extract_file_path(line)
            index_status, work_tree_status = xy_status[0], xy_status[1]
            if xy_status == "??":
                untracked.append(path)
                continue
            if index_status in "MADRC":
                staged.append(f"{index_status}  {path}")
            if work_tree_status in "MD":
                unstaged.append(f"{work_tree_status}  {path}")
            if index_status == "A" and work_tree_status == "M":
                if f"M  {path}" not in unstaged:
                    unstaged.append(f"M  {path}")
        if staged:
            self.staged_list.addItems(sorted(staged))
        if unstaged:
            self.unstaged_list.addItems(sorted(unstaged))
        if untracked:
            self.untracked_list.addItems(sorted(untracked))

    def _parse_and_display_history(self, log_output):
        # (Unchanged)
        self.clear_history_view()
        lines = log_output.strip().split("\n")
        if not log_output.strip():
            return
        self.history_table.setUpdatesEnabled(False)
        self.history_table.setSortingEnabled(False)
        rows = []
        for line in lines:  # ... (rest of parsing logic) ...
            if not line:
                continue
            parts = line.split("\t", 3)
            if len(parts) == 4:
                rows.append(parts)
        self.history_table.setRowCount(len(rows))
        for row_idx, row_data in enumerate(
            rows
        ):  # ... (rest of item creation logic) ...
            commit_hash_short = row_data[0][:7]
            author = QTableWidgetItem(row_data[1])
            date = QTableWidgetItem(row_data[2])
            subject = QTableWidgetItem(row_data[3])
            hash_item = QTableWidgetItem(commit_hash_short)
            hash_item.setData(Qt.ItemDataRole.UserRole, row_data[0])
            self.history_table.setItem(row_idx, 0, hash_item)
            self.history_table.setItem(row_idx, 1, author)
            self.history_table.setItem(row_idx, 2, date)
            self.history_table.setItem(row_idx, 3, subject)
        self.history_table.setSortingEnabled(True)
        self.history_table.setUpdatesEnabled(True)

    def _parse_and_display_branches(self, refs_output):
        # (Unchanged)
        self.clear_branches_view()
        root_node = self.branches_model.invisibleRootItem()
        local_node = QStandardItem("Local")
        local_node.setEditable(False)
        remotes_root_node = QStandardItem("Remotes")
        remotes_root_node.setEditable(False)
        remote_nodes = {}
        lines = refs_output.strip().split("\n")
        current_local_branch = None
        if not refs_output.strip():
            return
        bold_font = QFont()
        bold_font.setBold(True)
        has_local = False
        has_remotes = False
        for line in lines:  # ... (rest of parsing logic) ...
            if not line:
                continue
            is_head = line.startswith("*")
            ref_name = line.lstrip("*")
            item_text = ref_name
            if ref_name.startswith("refs/heads/"):
                branch_name = ref_name[len("refs/heads/") :]
                item_text = branch_name
                item = QStandardItem(item_text)
                item.setEditable(False)
                item.setData(branch_name, Qt.ItemDataRole.UserRole)
            if is_head:
                item.setFont(bold_font)
                current_local_branch = branch_name
                local_node.appendRow(item)
                has_local = True
            elif ref_name.startswith("refs/remotes/"):
                parts = ref_name[len("refs/remotes/") :].split("/", 1)
            if len(parts) == 2:
                remote_name, branch_name = parts
                item_text = branch_name
            if remote_name not in remote_nodes:
                remote_node = QStandardItem(remote_name)
                remote_node.setEditable(False)
                remote_nodes[remote_name] = remote_node
                remotes_root_node.appendRow(remote_node)
                has_remotes = True
            item = QStandardItem(item_text)
            item.setEditable(False)
            item.setData(ref_name, Qt.ItemDataRole.UserRole)
            remote_nodes[remote_name].appendRow(item)
        if has_local:
            root_node.appendRow(local_node)
        if has_remotes:
            root_node.appendRow(remotes_root_node)
        self.branches_view.expandAll()
        self.current_branch = current_local_branch

    def _display_diff(self, diff_output: str):
        """Displays the diff output in the diff_view, with simple syntax highlighting."""
        # Ensure diff view exists (might not if UI init fails)
        if not hasattr(self, 'diff_view') or not self.diff_view:
             print("Error: Diff view widget not available.")
             return

        self.diff_view.clear()
        cursor = self.diff_view.textCursor()
        for line in diff_output.splitlines():
            cursor.movePosition(cursor.MoveOperation.End)
            line_text = line + '\n' # Add newline back
            # Get current format to modify, otherwise might inherit previous line's format
            fmt = QTextCharFormat() # Start fresh or use self.diff_view.currentCharFormat()? Fresh is safer.

            if line.startswith('+'): fmt.setForeground(DIFF_ADDED_COLOR)
            elif line.startswith('-'): fmt.setForeground(DIFF_REMOVED_COLOR)
            elif line.startswith('diff --git') or line.startswith('index ') or line.startswith('---') or line.startswith('+++'):
                 fmt.setForeground(DIFF_HEADER_COLOR); fmt.setFontWeight(QFont.Weight.Bold)
            elif line.startswith('@@'):
                 fmt.setForeground(DIFF_HEADER_COLOR); fmt.setFontWeight(QFont.Weight.Normal)
            else: # Default line
                 fmt.setForeground(DIFF_DEFAULT_COLOR); fmt.setFontWeight(QFont.Weight.Normal)

            cursor.insertText(line_text, fmt) # Apply format with text
        self.diff_view.moveCursor(cursor.MoveOperation.Start) # Scroll to top

    # --- UI State & Helpers ---

    def clear_status_lists(self):
        self.staged_list.clear()
        self.unstaged_list.clear()
        self.untracked_list.clear()

    def clear_history_view(self):
        """Clears the history graph widget."""
        # Check if graph widget exists before calling its method
        if self.graph_widget:
            self.graph_widget.setData([]) # Tell widget to clear its data/drawing
        # Also clear table if it exists as a fallback? No, assume replacement.

    def clear_commit_box(self):
        self.commit_message_box.clear()

    def clear_branches_view(self):
        self.branches_model.clear()

    def clear_diff_view(self):
        self.diff_view.clear()
        self.diff_label.setText("Diff:")

    def clear_all_views(self):
        """Clears status lists, history graph, branches tree, diff view, detail view and commit message box."""
        self.clear_status_lists()
        self.clear_history_view() # Clears graph data
        self.clear_branches_view()
        self.clear_diff_view()
        self.clear_commit_box()
        # Also clear commit detail view fields
        self.detail_hash_value.clear()
        self.detail_author_value.clear()
        self.detail_date_value.clear()
        self.detail_message_view.clear()
        self.detail_files_list.clear()
        self._selected_commit_hash_details = None # Reset selected hash
        self._show_commit_detail_view(False) # Ensure commit box is shown

    def update_button_states(self):
        """Enable/disable buttons based on repo status, busy state, selections, etc."""
        repo_loaded = bool(self.repo_path)
        is_busy = self.current_git_thread and self.current_git_thread.isRunning()
        current_branch_exists = bool(self.current_branch)

        # --- Top Bar Buttons ---
        self.status_button.setEnabled(repo_loaded and not is_busy)
        self.refresh_history_button.setEnabled(repo_loaded and not is_busy)
        self.refresh_branches_button.setEnabled(repo_loaded and not is_busy)
        self.new_branch_button.setEnabled(repo_loaded and not is_busy)
        self.fetch_button.setEnabled(repo_loaded and not is_busy)
        self.pull_button.setEnabled(repo_loaded and not is_busy and current_branch_exists)
        self.push_button.setEnabled(repo_loaded and not is_busy and current_branch_exists)

        # --- Action Buttons ---
        if is_busy: # If busy, disable actions & commit box
            self.stage_button.setEnabled(False)
            self.unstage_button.setEnabled(False)
            self.commit_button.setEnabled(False)
            self.commit_message_box.setReadOnly(True)
            return # Don't need to check individual states if busy
        else:
            self.commit_message_box.setReadOnly(False) # Re-enable if not busy

        # --- State-dependent Buttons ---
        # <<< MODIFIED: Stage button enabled if EITHER unstaged OR untracked files are selected >>>
        has_unstaged_selection = len(self.unstaged_list.selectedItems()) > 0
        has_untracked_selection = len(self.untracked_list.selectedItems()) > 0
        self.stage_button.setEnabled((has_unstaged_selection or has_untracked_selection) and repo_loaded)

        # Unstage button logic remains the same
        has_staged_selection = len(self.staged_list.selectedItems()) > 0
        self.unstage_button.setEnabled(has_staged_selection and repo_loaded)

        # Commit button logic remains the same
        has_staged_files = self.staged_list.count() > 0
        has_commit_message = bool(self.commit_message_box.toPlainText().strip())
        self.commit_button.setEnabled(repo_loaded and has_staged_files and has_commit_message)

    def set_ui_busy(self, busy: bool):
        """Disable/enable UI elements during background operations."""
        disabled = busy
        # Top bar buttons
        self.open_button.setDisabled(disabled)
        self.status_button.setDisabled(disabled)
        self.refresh_history_button.setDisabled(disabled)
        self.refresh_branches_button.setDisabled(disabled)
        self.new_branch_button.setDisabled(disabled)
        self.fetch_button.setDisabled(disabled)
        self.pull_button.setDisabled(disabled)
        self.push_button.setDisabled(disabled)

        # Action buttons and commit area
        self.stage_button.setDisabled(disabled)
        self.unstage_button.setDisabled(disabled)
        self.commit_button.setDisabled(disabled)
        self.commit_message_box.setReadOnly(disabled)

        # Disable interaction with lists/trees/graph when busy
        self.branches_view.setEnabled(not disabled)
        self.staged_list.setEnabled(not disabled)
        self.unstaged_list.setEnabled(not disabled)
        self.untracked_list.setEnabled(not disabled)
        # <<< FIX: Use the graph container widget >>>
        if self.graph_widget_container: # Check if it was initialized successfully
            self.graph_widget_container.setEnabled(not disabled)
        # self.history_table.setEnabled(not disabled) # <<< REMOVE THIS LINE
        self.diff_view.setReadOnly(disabled) # Keep diff view read-only matching busy state

        if busy:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        else:
            QApplication.restoreOverrideCursor()
            # Update all button states when becoming not busy
            # Crucially, this happens *after* the cursor is restored
            # Use QTimer to ensure it happens after potential immediate UI updates
            QTimer.singleShot(0, self.update_button_states)

    # --- Application Exit Handling ---
    def closeEvent(self, event):
        # (Unchanged)
        wait_cursor = None
        if self.current_git_thread and self.current_git_thread.isRunning():
            print(f"Waiting for '{self.current_operation_name}' to finish...")
            self.setEnabled(False)
            wait_cursor = QApplication.overrideCursor()
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.current_git_thread.wait()
            QApplication.restoreOverrideCursor()
        if wait_cursor:
            QApplication.setOverrideCursor(wait_cursor)
            print("Finished. Closing.")
            event.accept()
        else:
            event.accept()
