import re


def parse_unified_diff(diff: str) -> dict:
    """
    Parse a unified diff and return a dict with file paths and line numbers.

    Input: Unified diff string
    Output: {
        "path/to/file.py": {
            "added_lines": [12, 15, 18],
            "removed_lines": [10, 11]
        }
    }
    """
    result = {}
    current_file = None
    line_offset = 0

    for line in diff.split("\n"):
        if line.startswith("diff --git"):
            match = re.search(r'b/(.+)$', line)
            if match:
                current_file = match.group(1)
                result[current_file] = {"added_lines": [], "removed_lines": []}
                line_offset = 0
        elif line.startswith("@@") and current_file:
            match = re.search(r'\+(\d+)(?:,(\d+))?', line)
            if match:
                line_offset = int(match.group(1)) - 1
        elif current_file and line.startswith("+"):
            line_offset += 1
            if not line.startswith("+++"):
                result[current_file]["added_lines"].append(line_offset)
        elif current_file and line.startswith(" "):
            line_offset += 1

    return result
