import os
import time
import uuid
import hashlib
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple
from archon.core.parser import get_file_language, analyze_file, get_language_name

# Standard folders to ignore
IGNORED_FOLDERS = {
    '.git',
    'node_modules',
    'venv',
    'env',
    'build',
    'dist',
    '__pycache__',
    '.idea',
    '.vscode'
}

# Categorize extensions for Report 06/08
EXTENSION_CATEGORIES = {
    # Source Code
    '.py': 'Source Code',
    '.java': 'Source Code',
    '.c': 'Source Code',
    '.h': 'Source Code',
    '.cpp': 'Source Code',
    '.cc': 'Source Code',
    '.cxx': 'Source Code',
    '.hpp': 'Source Code',
    '.js': 'Source Code',
    '.mjs': 'Source Code',
    '.cjs': 'Source Code',
    '.ts': 'Source Code',
    '.tsx': 'Source Code',
    '.php': 'Source Code',
    '.dart': 'Source Code',
    '.kt': 'Source Code',
    '.kts': 'Source Code',
    
    # Configuration
    '.xml': 'Configuration',
    '.json': 'Configuration',
    '.yaml': 'Configuration',
    '.yml': 'Configuration',
    '.toml': 'Configuration',
    '.ini': 'Configuration',
    '.config': 'Configuration',
    
    # Documentation
    '.md': 'Documentation',
    '.txt': 'Documentation',
    '.rst': 'Documentation',
    'LICENSE': 'Documentation',
    'CHANGELOG': 'Documentation',
    
    # Assets
    '.png': 'Assets',
    '.jpg': 'Assets',
    '.jpeg': 'Assets',
    '.gif': 'Assets',
    '.svg': 'Assets',
    '.ico': 'Assets',
    '.mp3': 'Assets',
    '.mp4': 'Assets',
    '.wav': 'Assets',
    '.pdf': 'Assets',
}


def is_binary_file(filepath: Path) -> bool:
    """
    Checks if a file is binary by looking for null bytes in the first 1024 bytes.
    """
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            return b'\0' in chunk
    except Exception:
        # If we can't read it, treat as binary/inaccessible
        return True


def get_extension_category(filepath: Path) -> str:
    """
    Categorizes file extensions into Source Code, Configuration, Documentation, Assets, or Others.
    Handles exact filenames like LICENSE or CHANGELOG.
    """
    name = filepath.name
    if name in EXTENSION_CATEGORIES:
        return EXTENSION_CATEGORIES[name]
        
    ext = filepath.suffix.lower()
    return EXTENSION_CATEGORIES.get(ext, 'Others')


def compute_sha256(filepath: Path) -> str:
    """Computes the SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            for chunk in iter(lambda: f.read(65536), b''):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return "N/A"


def get_mime_type(filepath: Path) -> str:
    """Guesses the MIME type of a file."""
    mime, _ = mimetypes.guess_type(filepath)
    return mime or "application/octet-stream"


def is_read_only(filepath: Path) -> bool:
    """Checks if a file is read-only."""
    try:
        return not os.access(filepath, os.W_OK)
    except Exception:
        return False


def is_executable(filepath: Path) -> bool:
    """Checks if a file is executable."""
    try:
        if os.name == 'nt':
            ext = filepath.suffix.lower()
            return os.access(filepath, os.X_OK) or ext in ('.exe', '.bat', '.cmd', '.ps1', '.lnk')
        return os.access(filepath, os.X_OK)
    except Exception:
        return False


class RepositoryScanner:
    def __init__(self, root_path: Path):
        self.root_path = root_path.resolve()
        
        # Load configuration
        from archon.modules.settings_manager import load_config
        self.config = load_config(self.root_path / "archon-config.json")
        
        # Build set of ignored folders
        rules = self.config.get('ignore_rules', {})
        self.ignored_folders = set(IGNORED_FOLDERS)
        if 'ignore_directories' in rules:
            self.ignored_folders.update(rules['ignore_directories'])
            
        # Files ignore patterns
        self.ignored_files_patterns = rules.get('ignore_files', [])
        
        # Ignored extensions
        self.ignored_extensions = set(e.lower().strip('.') for e in rules.get('ignore_extensions', []))
        
        # Hidden files/dirs checkboxes
        self.ignore_hidden_files = rules.get('ignore_hidden_files', True)
        self.ignore_hidden_directories = rules.get('ignore_hidden_directories', True)
        
        # File sizes
        self.max_file_size = rules.get('max_file_size', 10485760)
        
        # Scan stats
        self.scan_id = ""
        self.start_time = 0.0
        self.scan_duration = 0.0
        self.errors: List[Dict[str, str]] = []
        self.warnings: List[Dict[str, str]] = []
        
        # Collected data
        self.files_scanned: List[Dict[str, Any]] = []
        self.files_ignored: List[Dict[str, Any]] = []  # List of {"file": path, "reason": reason, ...}
        self.dirs_visited: Set[Path] = set()
        
        # Counts
        self.binary_count = 0
        self.hidden_count = 0
        self.unsupported_count = 0
        self.ignored_count = 0
        self.symlink_count = 0
        self.executable_count = 0
        
    def scan(self, progress_callback=None) -> Dict[str, Any]:
        """
        Recursively scans the project directory, skipping ignored folders.
        Classifies all files, calculates metrics, and tracks folder structures.
        """
        self.start_time = time.time()
        self.scan_id = str(uuid.uuid4())
        
        # Phase 1: Collect all files to build total list for progress indication
        file_paths = []
        self._traverse_collect(self.root_path, file_paths)
        
        total_files = len(file_paths)
        
        # Phase 2: Process collected files with optional progress callback
        for index, entry_path in enumerate(file_paths, 1):
            if progress_callback:
                progress_callback(index, total_files, entry_path)
                
            name = entry_path.name
            rel_path = entry_path.relative_to(self.root_path)
            
            # Universal properties for both scanned and ignored files
            file_size = 0
            is_symlink = entry_path.is_symlink()
            read_only = is_read_only(entry_path)
            executable = is_executable(entry_path)
            
            try:
                # Use lstat for symlinks so we don't follow them if they point elsewhere
                file_size = entry_path.lstat().st_size
            except Exception:
                pass
                
            sha256 = compute_sha256(entry_path)
            mime_type = get_mime_type(entry_path)
            
            if is_symlink:
                self.symlink_count += 1
            if executable:
                self.executable_count += 1
            
            # 1. Check for Hidden Files (starts with .)
            if name.startswith('.'):
                self.hidden_count += 1
                self.files_ignored.append({
                    'file': str(rel_path),
                    'reason': 'Hidden File',
                    'size_bytes': file_size,
                    'mime_type': mime_type,
                    'sha256': sha256,
                    'read_only': read_only,
                    'executable': executable,
                    'is_symlink': is_symlink
                })
                continue
                
            # 2. Check for Binary Files
            if is_binary_file(entry_path):
                self.binary_count += 1
                self.files_ignored.append({
                    'file': str(rel_path),
                    'reason': 'Binary File',
                    'size_bytes': file_size,
                    'mime_type': mime_type,
                    'sha256': sha256,
                    'read_only': read_only,
                    'executable': executable,
                    'is_symlink': is_symlink
                })
                continue
                
            # 3. Detect Language
            lang_id = get_file_language(entry_path)
            if not lang_id:
                # File is unsupported text file
                self.unsupported_count += 1
                self.files_ignored.append({
                    'file': str(rel_path),
                    'reason': 'Unsupported File',
                    'size_bytes': file_size,
                    'mime_type': mime_type,
                    'sha256': sha256,
                    'read_only': read_only,
                    'executable': executable,
                    'is_symlink': is_symlink
                })
                continue
            
            # 4. Scanned File - analyze
            try:
                metrics = analyze_file(entry_path, lang_id)
                
                self.files_scanned.append({
                    'file': str(rel_path),
                    'name': name,
                    'language': get_language_name(lang_id),
                    'lang_id': lang_id,
                    'extension': entry_path.suffix.lower(),
                    'directory': str(entry_path.parent.relative_to(self.root_path)) if entry_path.parent != self.root_path else '.',
                    'size_bytes': file_size,
                    'mime_type': mime_type,
                    'sha256': sha256,
                    'read_only': read_only,
                    'executable': executable,
                    'is_symlink': is_symlink,
                    'physical_loc': metrics['physical_loc'],
                    'logical_loc': metrics['logical_loc'],
                    'blank_lines': metrics['blank_lines'],
                    'comment_lines': metrics['comment_lines'],
                    'comment_density': metrics['comment_density'],
                    'char_count': metrics['char_count'],
                    'inline_comment_lines': metrics['inline_comment_lines']
                })
            except Exception as e:
                warning_msg = f"Failed to analyze {rel_path}: {e}"
                self.warnings.append({
                    'file': str(rel_path),
                    'message': warning_msg
                })
                self.files_ignored.append({
                    'file': str(rel_path),
                    'reason': f'Error during analysis: {e}',
                    'size_bytes': file_size,
                    'mime_type': mime_type,
                    'sha256': sha256,
                    'read_only': read_only,
                    'executable': executable,
                    'is_symlink': is_symlink
                })
                
        self.scan_duration = time.time() - self.start_time
        
        return self.get_results()

    def _traverse_collect(self, current_dir: Path, file_paths: List[Path]):
        """
        Walks the folder tree, skips ignored directories, and collects file paths.
        """
        import fnmatch
        try:
            for entry in os.scandir(current_dir):
                entry_path = Path(entry.path)
                name = entry.name
                
                # Check directory vs file
                if entry.is_dir():
                    is_ignored = (name in self.ignored_folders) or (name.startswith('.') and self.ignore_hidden_directories)
                    if is_ignored:
                        self.ignored_count += 1
                        self.files_ignored.append({
                            'file': str(entry_path.relative_to(self.root_path)),
                            'reason': 'Ignored Folder',
                            'size_bytes': 0,
                            'mime_type': 'inode/directory',
                            'sha256': 'N/A',
                            'read_only': False,
                            'executable': True,
                            'is_symlink': entry_path.is_symlink()
                        })
                        continue
                        
                    self.dirs_visited.add(entry_path)
                    self._traverse_collect(entry_path, file_paths)
                    
                elif entry.is_file():
                    # Check custom ignore rules
                    if name.startswith('.') and self.ignore_hidden_files:
                        self.hidden_count += 1
                        continue
                        
                    ext = entry_path.suffix.lower().strip('.')
                    if ext in self.ignored_extensions:
                        continue
                        
                    if any(fnmatch.fnmatch(name, pat) for pat in self.ignored_files_patterns):
                        continue
                        
                    if self.config.get('ignore_rules', {}).get('ignore_binary_files', True) and is_binary_file(entry_path):
                        self.binary_count += 1
                        continue
                        
                    try:
                        sz = entry_path.lstat().st_size
                    except Exception:
                        sz = 0
                    if sz > self.max_file_size:
                        continue
                        
                    file_paths.append(entry_path)
                    
        except Exception as e:
            err_msg = f"Failed to read directory {current_dir}: {e}"
            self.errors.append({
                'directory': str(current_dir.relative_to(self.root_path)) if current_dir != self.root_path else '.',
                'message': err_msg
            })

    def get_results(self) -> Dict[str, Any]:
        """
        Returns a compiled dictionary of all scanning metrics.
        """
        total_files = len(self.files_scanned) + len(self.files_ignored)
        
        return {
            'scan_id': self.scan_id,
            'root_path': self.root_path,
            'scan_duration': self.scan_duration,
            'files_scanned': self.files_scanned,
            'files_ignored': self.files_ignored,
            'dirs_visited': sorted(list(self.dirs_visited)),
            'counts': {
                'total_files': total_files,
                'supported_files': len(self.files_scanned),
                'ignored_files': len(self.files_ignored),
                'binary_files': self.binary_count,
                'unsupported_files': self.unsupported_count,
                'hidden_files': self.hidden_count,
                'total_directories': len(self.dirs_visited) + 1,  # Include root
                'symlinks': self.symlink_count,
                'executables': self.executable_count
            },
            'errors': self.errors,
            'warnings': self.warnings
        }
