
import re
from typing import List, Dict, Any

def parse_diff(diff_content: str) -> List[Dict[str, Any]]:
    """Parses a git diff string and extracts file-level changes."""
    files = []
    current_file = None
    
    # Regex to find file headers in diff (e.g., a/path/to/file.py b/path/to/file.py)
    file_header_pattern = re.compile(r"^diff --git a/(.+) b/(.+)$", re.MULTILINE)
    
    # Regex to find hunk headers (e.g., @@ -start_line,num_lines +start_line,num_lines @@)
    hunk_header_pattern = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@")

    lines = diff_content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        
        file_match = file_header_pattern.match(line)
        if file_match:
            # New file section starts
            if current_file:
                files.append(current_file)
            
            file_path = file_match.group(2) # Use the 'b/' path
            current_file = {
                "file_path": file_path,
                "diff": [],
                "hunks": []
            }
            i += 1 # Skip the next line (+++ b/...) as it's part of the header
        elif current_file and line.startswith("diff --git"):
            # Another file starts, but we missed the +++ line for the previous one
            if current_file:
                files.append(current_file)
            current_file = None # Reset to find the next file header
        elif current_file:
            hunk_match = hunk_header_pattern.match(line)
            if hunk_match:
                # New hunk starts
                source_start_line = int(hunk_match.group(1))
                target_start_line = int(hunk_match.group(2))
                current_hunk = {
                    "source_start_line": source_start_line,
                    "target_start_line": target_start_line,
                    "lines": []
                }
                current_file["hunks"].append(current_hunk)
                current_file["diff"].append(line) # Add hunk header to diff
            elif current_file["hunks"]:
                # Add line to current hunk and diff
                current_file["hunks"][-1]["lines"].append(line)
                current_file["diff"].append(line)
            else:
                # Lines before first hunk or not part of a hunk, add to general diff
                current_file["diff"].append(line)
        i += 1

    if current_file:
        files.append(current_file)
        
    # Join diff lines for each file
    for f in files:
        if not f["hunks"]:
            f["diff"] = ""
        else:
            f["diff"] = "\n".join(f["diff"])

    return files
