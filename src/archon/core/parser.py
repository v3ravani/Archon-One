from pathlib import Path
from typing import Dict, Any, Tuple, Optional

# Mapping of file extensions to language IDs
EXTENSION_TO_LANGUAGE = {
    '.py': 'python',
    '.java': 'java',
    '.c': 'c',
    '.h': 'c',
    '.cpp': 'cpp',
    '.cc': 'cpp',
    '.cxx': 'cpp',
    '.hpp': 'cpp',
    '.js': 'javascript',
    '.mjs': 'javascript',
    '.cjs': 'javascript',
    '.ts': 'typescript',
    '.tsx': 'typescript',
    '.html': 'html',
    '.htm': 'html',
    '.css': 'css',
    '.php': 'php',
    '.dart': 'dart',
    '.kt': 'kotlin',
    '.kts': 'kotlin',
    '.xml': 'xml',
    '.json': 'json',
    '.yaml': 'yaml',
    '.yml': 'yaml',
    '.md': 'markdown',
    '.go': 'go',
    '.rs': 'rust',
}

# Mapping of language IDs to names for reports
LANGUAGE_NAMES = {
    'python': 'Python',
    'java': 'Java',
    'c': 'C',
    'cpp': 'C++',
    'javascript': 'JavaScript',
    'typescript': 'TypeScript',
    'html': 'HTML',
    'css': 'CSS',
    'php': 'PHP',
    'dart': 'Dart',
    'kotlin': 'Kotlin',
    'xml': 'XML',
    'json': 'JSON',
    'yaml': 'YAML',
    'markdown': 'Markdown',
    'go': 'Go',
    'rust': 'Rust',
}

# Comment and string delimiters rules for each language
LANGUAGE_RULES = {
    'python': {
        'line_comments': ['#'],
        'block_comments': [('"""', '"""'), ("'''", "'''")],
        'string_delims': ['"""', "'''", '"', "'"]
    },
    'java': {
        'line_comments': ['//'],
        'block_comments': [('/*', '*/')],
        'string_delims': ['"', "'"]
    },
    'c': {
        'line_comments': ['//'],
        'block_comments': [('/*', '*/')],
        'string_delims': ['"', "'"]
    },
    'cpp': {
        'line_comments': ['//'],
        'block_comments': [('/*', '*/')],
        'string_delims': ['"', "'"]
    },
    'javascript': {
        'line_comments': ['//'],
        'block_comments': [('/*', '*/')],
        'string_delims': ['"', "'", '`']
    },
    'typescript': {
        'line_comments': ['//'],
        'block_comments': [('/*', '*/')],
        'string_delims': ['"', "'", '`']
    },
    'html': {
        'line_comments': [],
        'block_comments': [('<!--', '-->')],
        'string_delims': ['"', "'"]
    },
    'css': {
        'line_comments': [],
        'block_comments': [('/*', '*/')],
        'string_delims': ['"', "'"]
    },
    'php': {
        'line_comments': ['//', '#'],
        'block_comments': [('/*', '*/')],
        'string_delims': ['"', "'"]
    },
    'dart': {
        'line_comments': ['//'],
        'block_comments': [('/*', '*/')],
        'string_delims': ['"', "'"]
    },
    'kotlin': {
        'line_comments': ['//'],
        'block_comments': [('/*', '*/')],
        'string_delims': ['"', "'"]
    },
    'xml': {
        'line_comments': [],
        'block_comments': [('<!--', '-->')],
        'string_delims': ['"', "'"]
    },
    'json': {
        'line_comments': [],
        'block_comments': [],
        'string_delims': ['"']
    },
    'yaml': {
        'line_comments': ['#'],
        'block_comments': [],
        'string_delims': ['"', "'"]
    },
    'markdown': {
        'line_comments': [],
        'block_comments': [('<!--', '-->')],
        'string_delims': ['`']
    },
    'go': {
        'line_comments': ['//'],
        'block_comments': [('/*', '*/')],
        'string_delims': ['"', "'", '`']
    },
    'rust': {
        'line_comments': ['//'],
        'block_comments': [('/*', '*/')],
        'string_delims': ['"', "'"]
    }
}


def get_file_language(filepath: Path) -> Optional[str]:
    """
    Returns the language ID for a given file path based on its extension.
    Returns None if the file extension is not supported.
    """
    ext = filepath.suffix.lower()
    return EXTENSION_TO_LANGUAGE.get(ext)


def get_language_name(lang_id: str) -> str:
    """
    Returns the user-friendly name of the language from its ID.
    """
    return LANGUAGE_NAMES.get(lang_id, lang_id.capitalize())


def analyze_file(filepath: Path, language: str) -> Dict[str, Any]:
    """
    Statically analyzes a single file to compute line metrics:
    - Physical LOC
    - Logical LOC
    - Blank Lines
    - Comment Lines
    - Comment Density
    
    Uses a stateful character-by-character scanner to correctly parse
    inline comments, block comments, and escape sequences inside strings.
    """
    # Read the file content
    try:
        content = filepath.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        # Fallback to latin-1 to avoid failing
        content = filepath.read_text(encoding='latin-1')

    # Get rules for the language
    rules = LANGUAGE_RULES.get(language, {'line_comments': [], 'block_comments': [], 'string_delims': []})
    
    char_count = len(content)
    inline_comment_lines = 0
    
    # State variables across the whole file
    in_block_comment = False
    block_end_delim = None
    in_string = False
    string_delim = None

    physical_loc = 0
    blank_lines = 0
    comment_lines = 0
    logical_loc = 0

    lines = content.splitlines()

    for line in lines:
        physical_loc += 1
        stripped = line.strip()
        
        # Check for blank line
        if not stripped:
            blank_lines += 1
            continue

        has_code = False
        has_comment = False
        
        i = 0
        n = len(line)  # We parse the full line (with whitespace) to keep column offsets consistent
        
        while i < n:
            # 1. Handle Block Comment state
            if in_block_comment:
                if line[i:].startswith(block_end_delim):
                    has_comment = True
                    i += len(block_end_delim)
                    in_block_comment = False
                    block_end_delim = None
                else:
                    has_comment = True
                    i += 1
                continue

            # 2. Handle String state
            if in_string:
                # Check for escaped characters
                if line[i] == '\\' and i + 1 < n:
                    has_code = True
                    i += 2
                    continue
                
                if line[i:].startswith(string_delim):
                    has_code = True
                    i += len(string_delim)
                    in_string = False
                    string_delim = None
                else:
                    has_code = True
                    i += 1
                continue

            # 3. Normal state (neither in string nor block comment)
            # Check for block comment start
            found_block_start = False
            for start, end in rules['block_comments']:
                if line[i:].startswith(start):
                    # For Python triple quotes, we decide if it is a block comment or a string.
                    # Standard Python usage treats triple quotes as comments/docstrings when
                    # they are not part of an expression. To keep it simple and standard,
                    # we treat them as comments.
                    has_comment = True
                    in_block_comment = True
                    block_end_delim = end
                    i += len(start)
                    found_block_start = True
                    break
            if found_block_start:
                continue

            # Check for line comment start
            found_line_comment = False
            for l_comment in rules['line_comments']:
                if line[i:].startswith(l_comment):
                    has_comment = True
                    i = n  # Remainder of line is comment
                    found_line_comment = True
                    break
            if found_line_comment:
                break

            # Check for string start
            found_string_start = False
            for delim in rules['string_delims']:
                if line[i:].startswith(delim):
                    has_code = True
                    in_string = True
                    string_delim = delim
                    i += len(delim)
                    found_string_start = True
                    break
            if found_string_start:
                continue

            # Normal non-whitespace character is code
            if not line[i].isspace():
                has_code = True
            i += 1

        # Classify the line based on what was found
        # A line is counted as Code (Logical LOC) if it contains code (even with inline comments).
        # A line is Comment if it contains comments and NO code.
        # Otherwise it defaults to blank (should not happen if stripped is not empty).
        if has_code:
            logical_loc += 1
            if has_comment:
                inline_comment_lines += 1
        elif has_comment:
            comment_lines += 1
        else:
            blank_lines += 1

    # Comment Density Calculation
    # Density = (Comment Lines / Logical LOC) * 100
    if logical_loc > 0:
        comment_density = (comment_lines / logical_loc) * 100
    else:
        comment_density = 0.0

    return {
        'physical_loc': physical_loc,
        'logical_loc': logical_loc,
        'blank_lines': blank_lines,
        'comment_lines': comment_lines,
        'comment_density': comment_density,
        'char_count': char_count,
        'inline_comment_lines': inline_comment_lines
    }
