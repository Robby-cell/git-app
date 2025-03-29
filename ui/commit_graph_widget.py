from PyQt6.QtWidgets import QWidget, QScrollArea, QVBoxLayout, QSizePolicy
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFontMetrics, QFont
from PyQt6.QtCore import Qt, QRect, QPoint, QSize, pyqtSignal
from typing import List, Dict, Tuple, Optional, Any # For type hinting

# --- Constants ---
NODE_RADIUS = 5
NODE_DIAMETER = NODE_RADIUS * 2
H_SPACING = 25  # Horizontal space between columns - Increased slightly
V_SPACING = 30  # Vertical space between commit nodes - Increased slightly
OFFSET_X = 20   # Left padding - Increased
OFFSET_Y = 25   # Top padding - Increased
LINE_WIDTH = 2
BRANCH_COLORS = [ # Simple cycle of colors for branches
    QColor("#1f77b4"), QColor("#ff7f0e"), QColor("#2ca02c"), QColor("#d62728"),
    QColor("#9467bd"), QColor("#8c564b"), QColor("#e377c2"), QColor("#7f7f7f"),
    QColor("#bcbd22"), QColor("#17becf"), QColor("#aec7e8"), QColor("#ffbb78"),
    QColor("#98df8a"), QColor("#ff9896"), QColor("#c5b0d5"), QColor("#c49c94")
]
DEFAULT_NODE_COLOR = QColor("#AAAAAA") # For edges where lane isn't clear

class CommitGraphWidget(QWidget):
    """Widget to draw a simplified commit graph."""
    # Signal emitted when a node is clicked (optional)
    # commit_clicked = pyqtSignal(str) # Emits commit hash

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        # Commit data structure: list of dicts from parser
        self._commits_data: List[Dict[str, Any]] = []
        # Layout structures
        self._nodes: Dict[str, Dict[str, Any]] = {} # Map: commit_hash -> {x, y, color_idx}
        self._edges: List[Tuple[str, str, int]] = [] # List of tuples: (from_hash, to_hash, color_idx)
        # Dimensions
        self._max_x = 0
        self._max_y = 0
        # Basic setup
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Enable mouse tracking if needed for hover/click effects later
        # self.setMouseTracking(True)

    def _assign_layout(self):
        """
        Assigns X, Y coordinates and colors to commits for drawing.
        This is a very basic layout algorithm, prioritizing linearity and available lanes.
        Needs significant improvement for complex histories (merges, criss-crossing).
        """
        self._nodes = {}
        self._edges = []
        self._max_x = 0
        self._max_y = 0

        if not self._commits_data:
            self.updateGeometry()
            self.update()
            return

        lanes: Dict[int, int] = {}             # Map: lane_index -> last_commit_y in that lane
        lane_commits: Dict[int, str] = {}      # Map: lane_index -> commit_hash currently occupying it
        commit_lane: Dict[str, int] = {}       # Map: commit_hash -> assigned_lane_index
        commit_y_pos: Dict[str, int] = {}      # Map: commit_hash -> assigned_y_pos
        next_lane = 0
        y_pos = OFFSET_Y

        # Process commits roughly in reverse chronological order (as git log usually provides)
        # A strict topological sort might be better for complex graphs later
        processed_hashes = set()

        for i, commit in enumerate(self._commits_data):
            commit_hash = commit['hash']
            if commit_hash in processed_hashes: continue # Should not happen with git log, but safety

            # --- Find a Lane ---
            assigned_lane = -1
            parent_hashes = commit.get('parents', [])
            available_lanes = list(range(next_lane)) # Lanes potentially available

            # Try to inherit lane from first parent if available
            if parent_hashes:
                first_parent_hash = parent_hashes[0]
                if first_parent_hash in commit_lane:
                    parent_lane_idx = commit_lane[first_parent_hash]
                    # Is the lane free *at or before* this Y position?
                    if lanes.get(parent_lane_idx, -1) < y_pos:
                        assigned_lane = parent_lane_idx
                        if assigned_lane in available_lanes:
                             available_lanes.remove(assigned_lane) # Don't check it again

            # If no parent lane or parent lane occupied, find first available lane
            if assigned_lane == -1:
                for lane_idx in available_lanes:
                    if lanes.get(lane_idx, -1) < y_pos:
                        assigned_lane = lane_idx
                        break

            # If still no lane found, allocate a new one
            if assigned_lane == -1:
                assigned_lane = next_lane
                next_lane += 1

            # --- Assign Position and Color ---
            x_pos = OFFSET_X + assigned_lane * H_SPACING
            color_idx = assigned_lane % len(BRANCH_COLORS)
            self._nodes[commit_hash] = {'x': x_pos, 'y': y_pos, 'color_idx': color_idx}
            commit_lane[commit_hash] = assigned_lane
            commit_y_pos[commit_hash] = y_pos

            # Mark lane as occupied up to this Y position
            lanes[assigned_lane] = y_pos
            # lane_commits[assigned_lane] = commit_hash # Track occupant (optional for drawing)

            # Update max dimensions
            self._max_x = max(self._max_x, x_pos)
            self._max_y = y_pos

            processed_hashes.add(commit_hash)
            y_pos += V_SPACING # Increment Y for the next commit


        # --- Create Edges (after all nodes have potential positions) ---
        for commit_hash, node_info in self._nodes.items():
            # Find the original commit data to get parents
            original_commit = next((c for c in self._commits_data if c['hash'] == commit_hash), None)
            if not original_commit: continue

            parent_hashes = original_commit.get('parents', [])
            node_color_idx = node_info['color_idx']

            for parent_hash in parent_hashes:
                # Only create edge if parent node exists in our processed list
                if parent_hash in self._nodes:
                    # Use the child's color for the edge by default
                    self._edges.append((commit_hash, parent_hash, node_color_idx))
                # else: Parent is outside the range of commits we loaded


        # --- Update widget ---
        print(f"Layout assigned: {len(self._nodes)} nodes, {len(self._edges)} edges. MaxX: {self._max_x}, MaxY: {self._max_y}")
        self.updateGeometry() # Recalculate size hint based on content
        self.update() # Trigger repaint

    def setData(self, commits_data: List[Dict[str, Any]]):
        """Sets the commit data and triggers layout and repaint."""
        print(f"GraphWidget received {len(commits_data)} commits.")
        self._commits_data = commits_data
        # Ensure data has timestamps if sort key relies on it
        for commit in self._commits_data:
            if 'date_ts' not in commit: commit['date_ts'] = 0 # Add fallback if missing
        self._assign_layout()

    def sizeHint(self) -> QSize:
        """Provide a preferred size based on graph content."""
        # Add padding to max coordinates
        width = self._max_x + H_SPACING + OFFSET_X * 2 # Padding on both sides
        height = self._max_y + V_SPACING + OFFSET_Y # Padding below last node
        # print(f"Graph sizeHint: {width}x{height}")
        # Ensure minimum size if empty
        min_width = 100
        min_height = self.minimumHeight()
        return QSize(max(width, min_width), max(height, min_height))

    def paintEvent(self, event: Optional[Any]): # Type hint Any for QPaintEvent
        """Draws the commit graph."""
        if not self._nodes and not self._edges:
            return # Nothing to draw

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("white")) # White background

        # --- Draw Edges ---
        pen = QPen()
        pen.setWidth(LINE_WIDTH)
        for from_hash, to_hash, color_idx in self._edges:
            # Ensure both ends of the edge exist in the layout
            if from_hash in self._nodes and to_hash in self._nodes:
                node_from = self._nodes[from_hash]
                node_to = self._nodes[to_hash]

                # Choose color - Use child's color? Or parent's if available?
                edge_color = BRANCH_COLORS[color_idx % len(BRANCH_COLORS)]
                pen.setColor(edge_color)
                painter.setPen(pen)

                # Simple straight line connection
                # TODO: Implement curved lines for merges later
                painter.drawLine(node_from['x'], node_from['y'], node_to['x'], node_to['y'])
            # else: print(f"Skipping edge: {from_hash[:5]}->{to_hash[:5]} (Node missing)")


        # --- Draw Nodes ---
        node_pen = QPen(QColor("black")) # Black outline for nodes
        node_pen.setWidth(1)
        painter.setPen(node_pen)

        for commit_hash, node_info in self._nodes.items():
            color_idx = node_info['color_idx']
            brush_color = BRANCH_COLORS[color_idx % len(BRANCH_COLORS)]
            painter.setBrush(QBrush(brush_color))

            center_x = node_info['x']
            center_y = node_info['y']
            # Define the bounding box for the ellipse
            rect = QRect(center_x - NODE_RADIUS, center_y - NODE_RADIUS, NODE_DIAMETER, NODE_DIAMETER)
            painter.drawEllipse(rect)

        painter.end()

# --- Wrapper with Scroll Area ---
class ScrollableCommitGraphWidget(QScrollArea):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.graph_widget = CommitGraphWidget()
        self.setWidget(self.graph_widget)
        # Let the scroll area manage resizing based on the graph widget's size hint
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)


    def setData(self, commits_data: List[Dict[str, Any]]):
        """Passes data to the inner graph widget."""
        if self.graph_widget:
            self.graph_widget.setData(commits_data)
        else:
            print("Error: Inner graph widget not available in ScrollableCommitGraphWidget.")
