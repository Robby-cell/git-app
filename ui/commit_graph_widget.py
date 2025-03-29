# ui/commit_graph_widget.py

from PyQt6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QSizePolicy
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFontMetrics, QFont, QMouseEvent
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal
from typing import List, Dict, Tuple, Optional, Any  # For type hinting

# --- Constants ---
NODE_RADIUS = 5
NODE_DIAMETER = NODE_RADIUS * 2
H_SPACING = 25  # Horizontal space between columns
V_SPACING = 30  # Vertical space between commit nodes
OFFSET_X = 20  # Left padding
OFFSET_Y = 25  # Top padding
LINE_WIDTH = 2
BRANCH_COLORS = [  # Simple cycle of colors for branches
    QColor("#1f77b4"),
    QColor("#ff7f0e"),
    QColor("#2ca02c"),
    QColor("#d62728"),
    QColor("#9467bd"),
    QColor("#8c564b"),
    QColor("#e377c2"),
    QColor("#7f7f7f"),
    QColor("#bcbd22"),
    QColor("#17becf"),
    QColor("#aec7e8"),
    QColor("#ffbb78"),
    QColor("#98df8a"),
    QColor("#ff9896"),
    QColor("#c5b0d5"),
    QColor("#c49c94"),
]
DEFAULT_NODE_COLOR = QColor("#AAAAAA")  # For edges where lane isn't clear
SELECTED_PEN_COLOR = QColor("#FFD700")  # Gold for selection highlight


class CommitGraphWidget(QWidget):
    """Widget to draw a simplified commit graph."""

    # Signal emitted when a commit node is clicked
    commit_selected = pyqtSignal(str)  # Emits commit hash

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        # Commit data structure: list of dicts from parser
        # Expects dicts like: {"hash": str, "parents": List[str], "author": str, "date_ts": int, "msg": str}
        self._commits_data: List[Dict[str, Any]] = []
        # Layout structures calculated by _assign_layout
        self._nodes: Dict[
            str, Dict[str, Any]
        ] = {}  # Map: commit_hash -> {x, y, color_idx}
        self._edges: List[
            Tuple[str, str, int]
        ] = []  # List of tuples: (from_hash, to_hash, color_idx)
        # Dimensions calculated by _assign_layout
        self._max_x = 0
        self._max_y = 0
        # State
        self._selected_commit_hash: Optional[str] = None  # Track selected commit hash

        # Basic widget setup
        self.setMinimumHeight(200)  # Ensure it's visible even when empty
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Enable mouse tracking if needed for hover effects later
        # self.setMouseTracking(True)

    def _assign_layout(self):
        """
        Assigns X, Y coordinates and colors to commits for drawing.
        This is a very basic layout algorithm, prioritizing linearity and available lanes.
        Needs significant improvement for complex histories (merges, criss-crossing).
        """
        # Reset layout data structures
        self._nodes = {}
        self._edges = []
        self._max_x = 0
        self._max_y = 0

        # If no commit data, clear and exit
        if not self._commits_data:
            self.updateGeometry()  # Update size hint (will shrink)
            self.update()  # Trigger repaint (will clear)
            return

        # --- Layout Algorithm Data Structures ---
        lanes: Dict[
            int, int
        ] = {}  # Map: lane_index -> last_commit_y occupying that lane
        # lane_commits: Dict[int, str] = {}      # Map: lane_index -> commit_hash currently occupying it (optional)
        commit_lane: Dict[str, int] = {}  # Map: commit_hash -> assigned_lane_index
        commit_y_pos: Dict[
            str, int
        ] = {}  # Map: commit_hash -> assigned_y_pos (useful for debugging)
        next_lane = 0  # Counter for allocating new lanes
        y_pos = OFFSET_Y  # Current vertical position for placing nodes
        processed_hashes = set()  # Track processed commits to avoid duplicates

        # Process commits roughly in reverse chronological order (as git log usually provides)
        # Sorting explicitly by timestamp ensures consistency
        sorted_commits = sorted(
            self._commits_data, key=lambda c: c.get("date_ts", 0), reverse=True
        )

        for i, commit in enumerate(sorted_commits):
            commit_hash = commit["hash"]
            if commit_hash in processed_hashes:
                print(
                    f"Warning: Duplicate commit hash {commit_hash} encountered in layout."
                )
                continue  # Skip duplicates

            # --- Find a Lane for this Commit ---
            assigned_lane = -1
            parent_hashes = commit.get("parents", [])
            available_lanes = list(
                range(next_lane)
            )  # Lanes potentially available to reuse

            # Option 1: Try to inherit lane from first parent if it's free at this Y
            if parent_hashes:
                first_parent_hash = parent_hashes[0]
                if (
                    first_parent_hash in commit_lane
                ):  # Check if parent has been processed and assigned a lane
                    parent_lane_idx = commit_lane[first_parent_hash]
                    # Is the lane free *at or before* this Y position?
                    if lanes.get(parent_lane_idx, -1) < y_pos:
                        assigned_lane = parent_lane_idx
                        # Remove from available lanes check if we potentially take it
                        if assigned_lane in available_lanes:
                            available_lanes.remove(assigned_lane)

            # Option 2: If no parent lane or parent lane occupied, find first completely free lane
            if assigned_lane == -1:
                for lane_idx in available_lanes:
                    if (
                        lanes.get(lane_idx, -1) < y_pos
                    ):  # Check if lane is free up to this Y
                        assigned_lane = lane_idx
                        break

            # Option 3: If still no lane found, allocate a new one
            if assigned_lane == -1:
                assigned_lane = next_lane
                next_lane += 1

            # --- Assign Position and Color ---
            x_pos = OFFSET_X + assigned_lane * H_SPACING
            color_idx = assigned_lane % len(
                BRANCH_COLORS
            )  # Cycle through colors based on lane index

            # Store node layout information
            self._nodes[commit_hash] = {"x": x_pos, "y": y_pos, "color_idx": color_idx}
            commit_lane[commit_hash] = assigned_lane
            commit_y_pos[commit_hash] = y_pos

            # Mark lane as occupied up to this Y position
            lanes[assigned_lane] = y_pos
            # lane_commits[assigned_lane] = commit_hash # Track occupant (optional)

            # Update maximum dimensions seen so far for calculating widget size
            self._max_x = max(self._max_x, x_pos)
            self._max_y = y_pos

            processed_hashes.add(commit_hash)
            y_pos += V_SPACING  # Increment Y for the next commit row

        # --- Create Edges (after all nodes have potential positions) ---
        # This pass ensures we only draw edges between nodes that exist in the current view
        for commit_hash, node_info in self._nodes.items():
            # Find the original commit data to get parent list
            original_commit = next(
                (c for c in self._commits_data if c["hash"] == commit_hash), None
            )
            if not original_commit:
                print(
                    f"Warning: Original commit data not found for hash {commit_hash} when creating edges."
                )
                continue

            parent_hashes = original_commit.get("parents", [])
            node_color_idx = node_info[
                "color_idx"
            ]  # Use the child node's color index for the edge

            for parent_hash in parent_hashes:
                # Only create edge if parent node exists in our processed node list
                if parent_hash in self._nodes:
                    # Store edge information: (child_hash, parent_hash, color_index)
                    self._edges.append((commit_hash, parent_hash, node_color_idx))
                else:
                    # This means the parent is outside the range of commits we loaded (due to max-count)
                    # print(f"Debug: Parent {parent_hash[:7]} for commit {commit_hash[:7]} not found in loaded nodes.")
                    pass

        # --- Update widget geometry and trigger repaint ---
        print(
            f"Layout assigned: {len(self._nodes)} nodes, {len(self._edges)} edges. MaxX: {self._max_x}, MaxY: {self._max_y}"
        )
        self.updateGeometry()  # Recalculate size hint based on content
        self.update()  # Trigger repaint event

    def setData(self, commits_data: List[Dict[str, Any]]):
        """Sets the commit data, resets selection, and triggers layout/repaint."""
        print(f"GraphWidget received {len(commits_data)} commits.")
        # Store the raw data
        self._commits_data = commits_data
        # Reset selection when data changes
        self._selected_commit_hash = None
        # Ensure data has timestamps if sort key relies on it (done in parser is better)
        for commit in self._commits_data:
            if "date_ts" not in commit:
                print(
                    f"Warning: Commit {commit.get('hash', 'N/A')[:7]} missing 'date_ts'."
                )
                commit["date_ts"] = 0  # Add fallback if missing
        # Recalculate layout and trigger repaint
        self._assign_layout()

    def sizeHint(self) -> QSize:
        """Provide a preferred size based on graph content."""
        # Calculate width and height based on max coordinates plus padding
        width = (
            self._max_x + H_SPACING + OFFSET_X * 2
        )  # Padding on both sides for last lane/edges
        height = self._max_y + V_SPACING + OFFSET_Y  # Padding below last node
        # Ensure a minimum sensible size even if the graph is small or empty
        min_width = 150
        min_height = self.minimumHeight()  # Use the minimum height set in init
        calculated_size = QSize(max(width, min_width), max(height, min_height))
        # print(f"Graph sizeHint: {calculated_size.width()}x{calculated_size.height()}")
        return calculated_size

    def mousePressEvent(self, event: QMouseEvent):
        """Handle clicks to select commit nodes."""
        if event.button() == Qt.MouseButton.LeftButton:
            click_pos = (
                event.position().toPoint()
            )  # Get click position relative to widget
            clicked_hash = None
            # Define click sensitivity radius squared (slightly larger than node)
            min_dist_sq = (NODE_RADIUS * 1.5) ** 2

            # Iterate through drawn nodes to find if click hit one
            for commit_hash, node_info in self._nodes.items():
                node_center = QPoint(node_info["x"], node_info["y"])
                # Calculate squared distance from click to node center
                dist_sq = (click_pos.x() - node_center.x()) ** 2 + (
                    click_pos.y() - node_center.y()
                ) ** 2
                # If click is within sensitivity radius
                if dist_sq <= min_dist_sq:
                    clicked_hash = commit_hash
                    break  # Found the clicked node, no need to check others

            # If the clicked node is different from the currently selected one
            if clicked_hash != self._selected_commit_hash:
                self._selected_commit_hash = clicked_hash
                print(f"Node selected: {self._selected_commit_hash}")
                # Emit signal only if a valid node was clicked
                if self._selected_commit_hash:
                    self.commit_selected.emit(self._selected_commit_hash)
                # Trigger repaint to show the selection highlight change
                self.update()
            # If clicking outside nodes, maybe deselect?
            # elif clicked_hash is None and self._selected_commit_hash is not None:
            #     self._selected_commit_hash = None
            #     # Optionally emit signal with empty string or None for deselection?
            #     # self.commit_selected.emit("") # Or handle deselection differently
            #     self.update()
        else:
            # Pass other mouse button events to the base class
            super().mousePressEvent(event)

    def paintEvent(self, event: Optional[Any]):  # Type hint Any for QPaintEvent
        """Draws the commit graph, highlighting the selected node."""
        # If no nodes or edges calculated, nothing to draw
        if not self._nodes and not self._edges:
            # Optionally draw a placeholder text if empty?
            # painter = QPainter(self)
            # painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "No history to display.")
            # painter.end()
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        # Clear background
        painter.fillRect(self.rect(), Qt.GlobalColor.white)

        # --- Draw Edges ---
        edge_pen = QPen()
        edge_pen.setWidth(LINE_WIDTH)
        for from_hash, to_hash, color_idx in self._edges:
            # Ensure both ends of the edge exist in the current layout
            if from_hash in self._nodes and to_hash in self._nodes:
                node_from = self._nodes[from_hash]
                node_to = self._nodes[to_hash]

                # Determine edge color based on the child node's lane color
                edge_color = BRANCH_COLORS[color_idx % len(BRANCH_COLORS)]
                edge_pen.setColor(edge_color)
                painter.setPen(edge_pen)

                # Simple straight line connection
                # TODO: Implement curved lines for merges (would require more complex path calculation)
                painter.drawLine(
                    node_from["x"], node_from["y"], node_to["x"], node_to["y"]
                )

        # --- Draw Nodes ---
        node_pen = QPen(QColor("black"))  # Default outline color for nodes
        node_pen.setWidth(1)  # Default outline width
        selected_node_pen = QPen(SELECTED_PEN_COLOR)  # Outline color for selected node
        selected_node_pen.setWidth(3)  # Thicker outline for selected node

        # Iterate through all nodes to draw them
        for commit_hash, node_info in self._nodes.items():
            color_idx = node_info["color_idx"]
            brush_color = BRANCH_COLORS[color_idx % len(BRANCH_COLORS)]
            painter.setBrush(QBrush(brush_color))  # Fill color based on lane

            center_x = node_info["x"]
            center_y = node_info["y"]
            # Define the bounding rectangle for the ellipse
            rect = QRect(
                center_x - NODE_RADIUS,
                center_y - NODE_RADIUS,
                NODE_DIAMETER,
                NODE_DIAMETER,
            )

            # Set the outline pen based on whether the node is selected
            if commit_hash == self._selected_commit_hash:
                painter.setPen(selected_node_pen)
            else:
                painter.setPen(node_pen)

            # Draw the node
            painter.drawEllipse(rect)

        painter.end()


# --- Wrapper with Scroll Area (Provides scrolling for the graph) ---
class ScrollableCommitGraphWidget(QScrollArea):
    """A QScrollArea specialized for holding and scrolling the CommitGraphWidget."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        # Create the actual graph drawing widget
        self.graph_widget = CommitGraphWidget()
        # Set the inner widget for the scroll area
        self.setWidget(self.graph_widget)
        # Allow the scroll area to resize the inner widget based on its size hint
        self.setWidgetResizable(True)
        # Set scroll bar policies (show when needed)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Ensure the scroll area itself expands to fill available space
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def setData(self, commits_data: List[Dict[str, Any]]):
        """Passes the commit data down to the inner graph widget."""
        if self.graph_widget:
            self.graph_widget.setData(commits_data)
        else:
            # This should not happen if initialization is correct
            print(
                "Error: Inner graph widget is not available in ScrollableCommitGraphWidget."
            )

    # Expose the inner widget's signal if needed
    @property
    def commit_selected(self):
        if self.graph_widget:
            return self.graph_widget.commit_selected
        # Return a dummy signal or raise error if widget doesn't exist?
        # For simplicity, return None, connection logic must check existence
        return None
