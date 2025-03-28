import re

def extract_file_path(item_text):
    """Extracts the file path from the list item text (strips status prefix)."""
    # Assumes format like "XY  path" or just "path" for untracked
    # Handle potential 'R path -> newpath' or 'C path -> newpath' in future if needed
    match = re.match(r"^[ MADRC?]{1,2}\s+(.*)", item_text)
    if match:
        path = match.group(1).strip()
        # Basic handling for rename shown in status like 'R  orig -> new'
        if ' -> ' in path:
            return path.split(' -> ')[-1]
        return path
    else:
        # Handle untracked files or cases where prefix might be missing
        return item_text.strip()
