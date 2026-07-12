import os
import sys
import json
import time
import platform
import uuid
import getpass
import mimetypes
from pathlib import Path
from typing import Dict, Any, List, Optional
from tabulate import tabulate
import psutil

from archon.core.scanner import get_extension_category, IGNORED_FOLDERS

# Version files mapping to associate with languages
VERSION_FILES_MAP = {
    "requirements.txt": ("requirements.txt", "Python (pip)"),
    "pyproject.toml": ("pyproject.toml", "Python (setuptools/poetry)"),
    "package.json": ("package.json", "JavaScript/TypeScript (npm)"),
    "pom.xml": ("pom.xml", "Java (Maven)"),
    "build.gradle": ("build.gradle", "Java/Kotlin (Gradle)"),
    "pubspec.yaml": ("pubspec.yaml", "Dart/Flutter"),
    "go.mod": ("go.mod", "Go"),
    "Cargo.toml": ("Cargo.toml", "Rust"),
    "Gemfile": ("Gemfile", "Ruby"),
}

def format_size(bytes_count: int) -> str:
    """Formats file size in bytes to a human-readable string."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.2f} KB"
    else:
        return f"{bytes_count / (1024 * 1024):.2f} MB"


def get_diff_text(curr: float, prev: Optional[float], is_bytes: bool = False) -> str:
    """Generates absolute difference text (e.g. +10, -5, +2.4 KB, 0)."""
    if prev is None:
        return "[NEW]"
    diff = curr - prev
    if diff == 0:
        return "0 B" if is_bytes else "0"
    if is_bytes:
        sign = "+" if diff >= 0 else ""
        formatted_diff = format_size(int(diff)) if diff >= 0 else "-" + format_size(int(abs(diff)))
        return f"{sign}{formatted_diff}"
    if isinstance(diff, float) and not diff.is_integer():
        sign = "+" if diff >= 0 else ""
        return f"{sign}{diff:.2f}"
    return f"{int(diff):+d}"


def get_pct_diff_text(curr: float, prev: Optional[float], is_bytes: bool = False) -> str:
    """Generates percentage and absolute difference text (e.g. +5.26% (+10))."""
    if prev is None or prev == 0:
        return "[NEW]"
    diff = curr - prev
    pct = (diff / prev) * 100
    sign = "+" if pct >= 0 else ""
    if is_bytes:
        formatted_diff = format_size(int(diff)) if diff >= 0 else "-" + format_size(int(abs(diff)))
        return f"{sign}{pct:.2f}% ({formatted_diff})"
    if isinstance(diff, float) and not diff.is_integer():
        return f"{sign}{pct:.2f}% ({diff:+.2f})"
    return f"{sign}{pct:.2f}% ({int(diff):+,})"


def generate_ascii_tree(dir_path: Path, prefix: str = "", root_path: Path = None, current_depth: int = 1, max_depth: int = 5) -> List[str]:
    """Recursively builds a text-based ASCII directory tree, skipping ignored/hidden elements."""
    if root_path is None:
        root_path = dir_path
    
    lines = []
    if current_depth > max_depth:
        return [f"{prefix}└── ... (nesting depth limit reached)"]
        
    try:
        entries = sorted(list(dir_path.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
    except Exception:
        return []
        
    filtered = []
    for e in entries:
        if e.is_dir():
            if e.name in IGNORED_FOLDERS or e.name.startswith('.'):
                continue
        elif e.is_file():
            if e.name.startswith('.'):
                continue
        filtered.append(e)
        
    for index, entry in enumerate(filtered):
        is_last = (index == len(filtered) - 1)
        connector = "└── " if is_last else "├── "
        
        lines.append(f"{prefix}{connector}{entry.name}")
        
        if entry.is_dir():
            new_prefix = prefix + ("    " if is_last else "│   ")
            lines.extend(generate_ascii_tree(entry, new_prefix, root_path, current_depth + 1, max_depth))
            
    return lines


class CodeMetricsReporter:
    def __init__(self, results: Dict[str, Any], output_root: Path):
        self.results = results
        self.output_root = output_root
        self.root_path = Path(results['root_path'])
        
        # Extracted scanner results
        self.scanned = results['files_scanned']
        self.ignored = results['files_ignored']
        self.counts = results['counts']
        self.errors = results['errors']
        self.warnings = results['warnings']
        self.scan_duration = results['scan_duration']
        self.scan_id = results.get('scan_id', 'N/A')
        
        from archon.modules.settings_manager import load_config
        self.config = load_config(self.root_path / "archon-config.json")

    def _find_last_scan_folder(self) -> Optional[Path]:
        try:
            archon_one_root = self.output_root.parent.parent
            if not archon_one_root.exists():
                return None
            dirs = [d for d in archon_one_root.iterdir() if d.is_dir()]
            dirs = sorted(dirs, key=lambda x: x.name)
            current_name = self.output_root.parent.name
            current_index = -1
            for idx, d in enumerate(dirs):
                if d.name == current_name:
                    current_index = idx
                    break
            if current_index <= 0:
                return None
            prev_folder = dirs[current_index - 1] / "01_metrics"
            if prev_folder.exists():
                return prev_folder
        except Exception:
            pass
        return None

    def _load_previous_metrics(self) -> Dict[str, Any]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        metrics = {}
        summary_json_path = prev_folder / "01_repository_summary.json"
        if summary_json_path.exists():
            try:
                data = json.loads(summary_json_path.read_text(encoding='utf-8'))
                metrics['total_files'] = data.get('repository_overview', {}).get('total_files')
                metrics['supported_files'] = data.get('repository_overview', {}).get('supported_files')
                metrics['ignored_files'] = data.get('repository_overview', {}).get('ignored_files')
                metrics['repository_size_bytes'] = data.get('repository_overview', {}).get('repository_size_bytes')
                metrics['physical_loc'] = data.get('code_statistics', {}).get('physical_loc')
                metrics['logical_loc'] = data.get('code_statistics', {}).get('logical_loc')
            except Exception:
                pass
        return metrics

    def _load_previous_file_metrics(self) -> Dict[str, Dict[str, Any]]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        file_metrics = {}
        file_json_path = prev_folder / "02_file_metrics.json"
        if file_json_path.exists():
            try:
                data = json.loads(file_json_path.read_text(encoding='utf-8'))
                for item in data.get('scanned_files_metrics', []):
                    path = item.get('file')
                    if path:
                        file_metrics[path] = item
            except Exception:
                pass
        return file_metrics

    def _load_previous_directory_metrics(self) -> Dict[str, Dict[str, Any]]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        dir_metrics = {}
        dir_json_path = prev_folder / "03_directory_metrics.json"
        if dir_json_path.exists():
            try:
                data = json.loads(dir_json_path.read_text(encoding='utf-8'))
                for item in data.get('directory_metrics', []):
                    path = item.get('directory')
                    if path:
                        dir_metrics[path] = item
            except Exception:
                pass
        return dir_metrics

    def _load_previous_language_metrics(self) -> Dict[str, Dict[str, Any]]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        lang_metrics = {}
        lang_json_path = prev_folder / "04_language_metrics.json"
        if lang_json_path.exists():
            try:
                data = json.loads(lang_json_path.read_text(encoding='utf-8'))
                for item in data.get('language_metrics', []):
                    lang = item.get('language')
                    if lang:
                        lang_metrics[lang] = item
            except Exception:
                pass
        return lang_metrics

    def _load_previous_documentation_metrics(self) -> Dict[str, Any]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        doc_json_path = prev_folder / "05_documentation_metrics.json"
        if doc_json_path.exists():
            try:
                return json.loads(doc_json_path.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {}

    def _load_previous_extension_metrics(self) -> Dict[str, Dict[str, Any]]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        ext_metrics = {}
        ext_json_path = prev_folder / "06_extension_statistics.json"
        if ext_json_path.exists():
            try:
                data = json.loads(ext_json_path.read_text(encoding='utf-8'))
                for item in data.get('extensions_by_files', []):
                    ext = item.get('extension')
                    if ext:
                        ext_metrics[ext] = item
            except Exception:
                pass
        return ext_metrics

    def _load_previous_size_metrics(self) -> Dict[str, Any]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        size_json_path = prev_folder / "07_size_analysis.json"
        if size_json_path.exists():
            try:
                return json.loads(size_json_path.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {}

    def _load_previous_structure_metrics(self) -> Dict[str, Any]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        struct_json_path = prev_folder / "08_project_structure.json"
        if struct_json_path.exists():
            try:
                return json.loads(struct_json_path.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {}

    def _load_previous_scan_stats(self) -> Dict[str, Any]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        stats_json_path = prev_folder / "09_scan_statistics.json"
        if stats_json_path.exists():
            try:
                return json.loads(stats_json_path.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {}

    def _load_previous_metadata(self) -> Dict[str, Any]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        metadata_json_path = prev_folder / "10_metadata.json"
        if metadata_json_path.exists():
            try:
                return json.loads(metadata_json_path.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {}

    def _load_previous_dependencies(self) -> Dict[str, Any]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        deps_json_path = prev_folder / "11_dependencies.json"
        if deps_json_path.exists():
            try:
                return json.loads(deps_json_path.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {}

    def _get_footer(self) -> str:
        """Generates the unified footer for TXT reports."""
        local_time = time.localtime(self.results.get('start_time', time.time()))
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
        
        footer = [
            "\n\n=========================================",
            "Generated by Archon One",
            "Version: 0.2.0",
            f"Scan ID: {self.scan_id}",
            f"Repository Name: {self.root_path.name}",
            f"Timestamp: {timestamp_str}",
            f"Total Scan Duration: {self.scan_duration:.4f} seconds",
            "=========================================\n"
        ]
        return "\n".join(footer)

    def _write_files(self, base_name: str, txt_content: str, json_data: Any):
        """Helper to write both TXT and JSON files, adding the TXT footer."""
        txt_content_with_footer = txt_content + self._get_footer()
        
        if self.config.get('output', {}).get('txt', True):
            txt_path = self.output_root / f"{base_name}.txt"
            txt_path.write_text(txt_content_with_footer, encoding='utf-8')
            
        if self.config.get('output', {}).get('json', True):
            json_path = self.output_root / f"{base_name}.json"
            json_path.write_text(json.dumps(json_data, indent=2), encoding='utf-8')
            
        if self.config.get('output', {}).get('md', True):
            md_path = self.output_root / f"{base_name}.md"
            md_content = f"# Archon One Report - {base_name.replace('_', ' ').title()}\n\n```txt\n{txt_content_with_footer}\n```\n"
            md_path.write_text(md_content, encoding='utf-8')

    def generate_reports(self):
        """Generates all 11 reports in both .txt and .json formats."""
        # Create output directory
        self.output_root.mkdir(parents=True, exist_ok=True)
        
        # Run report generation methods
        self._report_01_summary()
        self._report_02_file_metrics()
        self._report_03_directory_metrics()
        self._report_04_language_metrics()
        self._report_05_documentation_metrics()
        self._report_06_extension_statistics()
        self._report_07_size_analysis()
        self._report_08_project_structure()
        self._report_09_scan_statistics()
        self._report_10_metadata()
        self._report_11_dependencies()
        
        # Generate interactive HTML report
        from archon.core.html_generator import compile_and_write_html_report
        nav = {"next": "../02_security/report.html"}
        compile_and_write_html_report(self.output_root, self.results, "Code Metrics (Module 01)", nav)

    def _report_01_summary(self):
        """01 Repository Summary"""
        local_time = time.localtime(self.results.get('start_time', time.time()))
        scan_date = time.strftime("%Y-%m-%d", local_time)
        scan_time = time.strftime("%H:%M:%S", local_time)
        
        languages = {f['language'] for f in self.scanned}
        total_scanned_size = sum(f['size_bytes'] for f in self.scanned)
        total_chars = sum(f.get('char_count', 0) for f in self.scanned)
        avg_file_size = total_scanned_size / len(self.scanned) if self.scanned else 0
        
        # 1. Repository Overview Table
        prev_metrics = self._load_previous_metrics()
        
        # Overview headers
        overview_headers = ["Metric", "Value"]
        if prev_metrics:
            overview_headers.append("Change")
            
        overview_data = [
            ["Repository Name", self.root_path.name] + (["N/A"] if prev_metrics else []),
            ["Scan Date", scan_date] + (["N/A"] if prev_metrics else []),
            ["Scan Time", scan_time] + (["N/A"] if prev_metrics else []),
            ["Total Files", self.counts['total_files']] + ([get_pct_diff_text(self.counts['total_files'], prev_metrics.get('total_files'))] if prev_metrics else []),
            ["Supported Files", self.counts['supported_files']] + ([get_pct_diff_text(self.counts['supported_files'], prev_metrics.get('supported_files'))] if prev_metrics else []),
            ["Ignored Files", self.counts['ignored_files']] + ([get_pct_diff_text(self.counts['ignored_files'], prev_metrics.get('ignored_files'))] if prev_metrics else []),
            ["Total Directories", self.counts['total_directories']] + (["N/A"] if prev_metrics else []),
            ["Total Languages", len(languages)] + (["N/A"] if prev_metrics else []),
            ["Total Characters Scanned", f"{total_chars:,}"] + (["N/A"] if prev_metrics else []),
            ["Repository Size", format_size(total_scanned_size)] + ([get_pct_diff_text(total_scanned_size, prev_metrics.get('repository_size_bytes'), is_bytes=True)] if prev_metrics else []),
            ["Average File Size", format_size(avg_file_size)] + (["N/A"] if prev_metrics else [])
        ]
        
        # 2. Code Statistics Table
        total_phys_loc = sum(f['physical_loc'] for f in self.scanned)
        total_logical_loc = sum(f['logical_loc'] for f in self.scanned)
        total_blank_lines = sum(f['blank_lines'] for f in self.scanned)
        total_comment_lines = sum(f['comment_lines'] for f in self.scanned)
        total_inline_comment_lines = sum(f.get('inline_comment_lines', 0) for f in self.scanned)
        
        if total_logical_loc > 0:
            comment_density = (total_comment_lines / total_logical_loc) * 100
            inline_density = (total_inline_comment_lines / total_logical_loc) * 100
        else:
            comment_density = 0.0
            inline_density = 0.0
            
        pure_code_lines = total_logical_loc - total_inline_comment_lines
        avg_loc_file = total_logical_loc / self.counts['total_files'] if self.counts['total_files'] > 0 else 0.0
        
        code_stats_headers = ["Metric", "Value"]
        if prev_metrics:
            code_stats_headers.append("Change")
            
        code_stats_data = [
            ["Physical LOC", f"{total_phys_loc:,}"] + ([get_pct_diff_text(total_phys_loc, prev_metrics.get('physical_loc'))] if prev_metrics else []),
            ["Logical LOC (Total Code)", f"{total_logical_loc:,}"] + ([get_pct_diff_text(total_logical_loc, prev_metrics.get('logical_loc'))] if prev_metrics else []),
            ["Pure Code Lines (excluding inline comments)", f"{pure_code_lines:,}"] + (["N/A"] if prev_metrics else []),
            ["Blank Lines", f"{total_blank_lines:,}"] + (["N/A"] if prev_metrics else []),
            ["Comment Lines (pure comments)", f"{total_comment_lines:,}"] + (["N/A"] if prev_metrics else []),
            ["Inline Comment Lines", f"{total_inline_comment_lines:,}"] + (["N/A"] if prev_metrics else []),
            ["Comment Density", f"{comment_density:.2f}%"] + (["N/A"] if prev_metrics else []),
            ["Inline Comment Density", f"{inline_density:.2f}%"] + (["N/A"] if prev_metrics else []),
            ["Average LOC/File", f"{avg_loc_file:.2f}"] + (["N/A"] if prev_metrics else [])
        ]
        
        # 3. Repository Highlights
        if self.scanned:
            largest_f = max(self.scanned, key=lambda x: x['size_bytes'])
            largest_file_val = f"{largest_f['file']} ({format_size(largest_f['size_bytes'])})"
        else:
            largest_file_val = "N/A"
            
        dir_sizes = {}
        for f in self.scanned:
            dir_path = f['directory']
            dir_sizes[dir_path] = dir_sizes.get(dir_path, 0) + f['size_bytes']
        if dir_sizes:
            largest_d = max(dir_sizes.items(), key=lambda x: x[1])
            largest_dir_val = f"{largest_d[0]} ({format_size(largest_d[1])})"
        else:
            largest_dir_val = "N/A"
            
        lang_locs = {}
        for f in self.scanned:
            lang = f['language']
            lang_locs[lang] = lang_locs.get(lang, 0) + f['physical_loc']
        if lang_locs:
            most_used_l = max(lang_locs.items(), key=lambda x: x[1])
            most_used_lang_val = f"{most_used_l[0]} ({most_used_l[1]:,} LOC)"
        else:
            most_used_lang_val = "N/A"
            
        ext_counts = {}
        for f in self.scanned:
            ext = f['extension']
            ext_counts[ext] = ext_counts.get(ext, 0) + 1
        if ext_counts:
            largest_e = max(ext_counts.items(), key=lambda x: x[1])
            largest_ext_val = f"{largest_e[0]} ({largest_e[1]} files)"
        else:
            largest_ext_val = "N/A"
            
        filtered_for_docs = [f for f in self.scanned if f['logical_loc'] >= 5]
        if filtered_for_docs:
            most_doc_f = max(filtered_for_docs, key=lambda x: x['comment_density'])
            least_doc_f = min(filtered_for_docs, key=lambda x: x['comment_density'])
            most_documented_val = f"{most_doc_f['file']} ({most_doc_f['comment_density']:.1f}%)"
            least_documented_val = f"{least_doc_f['file']} ({least_doc_f['comment_density']:.1f}%)"
        else:
            most_documented_val = "N/A"
            least_documented_val = "N/A"
            
        highlights_data = [
            ["Largest File", largest_file_val],
            ["Largest Directory", largest_dir_val],
            ["Most Used Language", most_used_lang_val],
            ["Largest Extension", largest_ext_val],
            ["Most Documented File (LOC >= 5)", most_documented_val],
            ["Least Documented File (LOC >= 5)", least_documented_val]
        ]
        
        # 4. Repository Fingerprint Table
        fingerprint_categories = ["Source Code", "Documentation", "Configuration", "Assets"]
        fingerprint_sizes = {cat: 0 for cat in fingerprint_categories}
        fingerprint_sizes["Others"] = 0
        
        # Gather sizes from both scanned and ignored
        all_items = self.scanned + self.ignored
        for item in all_items:
            path_str = item['file']
            cat = get_extension_category(Path(path_str))
            if cat in fingerprint_sizes:
                fingerprint_sizes[cat] += item.get('size_bytes', 0)
            else:
                fingerprint_sizes["Others"] += item.get('size_bytes', 0)
                
        total_executable_files = sum(1 for item in all_items if item.get('executable', False))
        total_symlinks = sum(1 for item in all_items if item.get('is_symlink', False))
        
        fingerprint_data = [
            ["Total Source Code Size", format_size(fingerprint_sizes["Source Code"])],
            ["Total Documentation Size", format_size(fingerprint_sizes["Documentation"])],
            ["Total Configuration Size", format_size(fingerprint_sizes["Configuration"])],
            ["Total Asset Size", format_size(fingerprint_sizes["Assets"])],
            ["Total Executable Files", total_executable_files],
            ["Total Symbolic Links", total_symlinks]
        ]

        # 5. Estimated Code Structure
        struct_counts = self._get_estimated_structure_counts()
        structure_data = [
            ["Estimated Classes / Structs", struct_counts['estimated_classes']],
            ["Estimated Functions / Methods", struct_counts['estimated_functions']]
        ]
        
        # 6. Developer Task Annotations (TODO/FIXME checklist)
        annotations = self._get_developer_annotations()
        annotations_txt = []
        for a in annotations:
            msg = a['message']
            if len(msg) > 50:
                msg = msg[:47] + "..."
            annotations_txt.append([a['file'], a['line'], a['tag'], msg])

        # Format text report
        txt = []
        txt.append("=========================================")
        txt.append("       01 REPOSITORY SUMMARY REPORT      ")
        txt.append("=========================================\n")
        
        if prev_metrics:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append("## Repository Overview")
        txt.append(tabulate(overview_data, headers=overview_headers, tablefmt="grid"))
        txt.append("\n## Code Statistics")
        txt.append(tabulate(code_stats_data, headers=code_stats_headers, tablefmt="grid"))
        txt.append("\n## Repository Highlights")
        txt.append(tabulate(highlights_data, headers=["Metric", "Value"], tablefmt="grid"))
        txt.append("\n## Repository Fingerprint")
        txt.append(tabulate(fingerprint_data, headers=["Metric", "Value"], tablefmt="grid"))
        
        txt.append("\n## Estimated Code Structure")
        txt.append(tabulate(structure_data, headers=["Metric", "Value"], tablefmt="grid"))
        
        txt.append("\n## Developer Task Annotations (TODO/FIXME Checklist)")
        if annotations_txt:
            txt.append(tabulate(annotations_txt, headers=["File", "Line", "Tag", "Message Details"], tablefmt="grid"))
        else:
            txt.append("No developer annotations (TODO/FIXME/HACK/BUG) found in comments.")
        
        txt_content = "\n".join(txt)
        
        # Format JSON report
        json_data = {
            "repository_overview": {
                "repository_name": self.root_path.name,
                "scan_date": scan_date,
                "scan_time": scan_time,
                "total_files": self.counts['total_files'],
                "supported_files": self.counts['supported_files'],
                "ignored_files": self.counts['ignored_files'],
                "total_directories": self.counts['total_directories'],
                "total_languages": len(languages),
                "total_characters_scanned": total_chars,
                "repository_size_bytes": total_scanned_size,
                "repository_size_formatted": format_size(total_scanned_size),
                "average_file_size_formatted": format_size(avg_file_size)
            },
            "code_statistics": {
                "physical_loc": total_phys_loc,
                "logical_loc": total_logical_loc,
                "pure_code_lines": pure_code_lines,
                "blank_lines": total_blank_lines,
                "comment_lines": total_comment_lines,
                "inline_comment_lines": total_inline_comment_lines,
                "comment_density_pct": round(comment_density, 2),
                "inline_comment_density_pct": round(inline_density, 2),
                "average_loc_per_file": round(avg_loc_file, 2)
            },
            "repository_highlights": {
                "largest_file": largest_file_val,
                "largest_directory": largest_dir_val,
                "most_used_language": most_used_lang_val,
                "largest_extension": largest_ext_val,
                "most_documented_file": most_documented_val,
                "least_documented_file": least_documented_val
            },
            "repository_fingerprint": {
                "total_source_code_size_bytes": fingerprint_sizes["Source Code"],
                "total_documentation_size_bytes": fingerprint_sizes["Documentation"],
                "total_configuration_size_bytes": fingerprint_sizes["Configuration"],
                "total_asset_size_bytes": fingerprint_sizes["Assets"],
                "total_executable_files": total_executable_files,
                "total_symbolic_links": total_symlinks
            },
            "code_structure": {
                "estimated_classes": struct_counts['estimated_classes'],
                "estimated_functions": struct_counts['estimated_functions']
            },
            "developer_annotations": annotations
        }
        
        if prev_metrics:
            json_data["changes_since_last_scan"] = {
                "previous_scan_folder": self._find_last_scan_folder().parent.name,
                "metrics": {
                    "total_files": get_pct_diff_text(self.counts['total_files'], prev_metrics.get('total_files')),
                    "supported_files": get_pct_diff_text(self.counts['supported_files'], prev_metrics.get('supported_files')),
                    "ignored_files": get_pct_diff_text(self.counts['ignored_files'], prev_metrics.get('ignored_files')),
                    "repository_size": get_pct_diff_text(total_scanned_size, prev_metrics.get('repository_size_bytes'), is_bytes=True),
                    "physical_loc": get_pct_diff_text(total_phys_loc, prev_metrics.get('physical_loc')),
                    "logical_loc": get_pct_diff_text(total_logical_loc, prev_metrics.get('logical_loc'))
                }
            }
            
        self._write_files("01_repository_summary", txt_content, json_data)

    def _report_02_file_metrics(self):
        """02 File Metrics"""
        sorted_files = sorted(self.scanned, key=lambda x: x['physical_loc'], reverse=True)
        prev_files = self._load_previous_file_metrics()
        
        headers = [
            "File", "Language", "Extension", "Directory", 
            "Size (KB)", "Characters", "Avg Line Len",
            "Physical LOC", "Logical LOC", "Blank Lines", 
            "Comment Lines", "Inline Comments", "Comment Density",
            "MIME Type", "File Hash (SHA-256)", "Read Only", "Executable", "Symlink"
        ]
        
        if prev_files:
            headers.extend(["Size Change", "LOC Change"])
            
        rows_txt = []
        rows_json = []
        
        for f in sorted_files:
            size_kb = f['size_bytes'] / 1024.0
            chars = f.get('char_count', 0)
            avg_line_len = chars / f['physical_loc'] if f['physical_loc'] > 0 else 0
            
            row = [
                f['file'],
                f['language'],
                f['extension'],
                f['directory'],
                f"{size_kb:.2f}",
                f"{chars:,}",
                f"{avg_line_len:.1f}",
                f"{f['physical_loc']:,}",
                f"{f['logical_loc']:,}",
                f"{f['blank_lines']:,}",
                f"{f['comment_lines']:,}",
                f"{f.get('inline_comment_lines', 0):,}",
                f"{f['comment_density']:.2f}%",
                f.get('mime_type', 'N/A'),
                f.get('sha256', 'N/A')[:10] + "...",
                "Yes" if f.get('read_only', False) else "No",
                "Yes" if f.get('executable', False) else "No",
                "Yes" if f.get('is_symlink', False) else "No"
            ]
            
            item_json = {
                "file": f['file'],
                "language": f['language'],
                "extension": f['extension'],
                "directory": f['directory'],
                "size_kb": round(size_kb, 2),
                "size_bytes": f['size_bytes'],
                "characters_count": chars,
                "average_line_length": round(avg_line_len, 1),
                "physical_loc": f['physical_loc'],
                "logical_loc": f['logical_loc'],
                "blank_lines": f['blank_lines'],
                "comment_lines": f['comment_lines'],
                "inline_comment_lines": f.get('inline_comment_lines', 0),
                "comment_density_pct": round(f['comment_density'], 2),
                "mime_type": f.get('mime_type', 'N/A'),
                "sha256_hash": f.get('sha256', 'N/A'),
                "read_only": f.get('read_only', False),
                "executable": f.get('executable', False),
                "is_symlink": f.get('is_symlink', False)
            }
            
            if prev_files:
                prev_file = prev_files.get(f['file'])
                if prev_file:
                    size_change = get_diff_text(f['size_bytes'], prev_file.get('size_bytes'), is_bytes=True)
                    loc_change = get_diff_text(f['physical_loc'], prev_file.get('physical_loc'))
                else:
                    size_change = "[NEW]"
                    loc_change = "[NEW]"
                row.extend([size_change, loc_change])
                item_json["change_since_last_scan"] = {
                    "size_change": size_change,
                    "loc_change": loc_change
                }
                
            rows_txt.append(row)
            rows_json.append(item_json)
            
        # Duplicate Files
        hash_groups = {}
        all_items = self.scanned + self.ignored
        for item in all_items:
            h = item.get('sha256', 'N/A')
            if h and h != 'N/A' and item.get('mime_type') != 'inode/directory':
                if h not in hash_groups:
                    hash_groups[h] = []
                hash_groups[h].append(item)
                
        duplicates_txt = []
        duplicates_json = []
        for h, items in hash_groups.items():
            if len(items) > 1:
                for item in items:
                    t = "Scanned" if 'physical_loc' in item else f"Ignored ({item.get('reason', 'Unknown')})"
                    duplicates_txt.append([h[:16] + "...", item['file'], format_size(item.get('size_bytes', 0)), t])
                    duplicates_json.append({
                        "sha256": h,
                        "file": item['file'],
                        "size_bytes": item.get('size_bytes', 0),
                        "type": t
                    })
                    
        # Zero-byte Files
        zerobyte_txt = []
        zerobyte_json = []
        for item in all_items:
            if item.get('mime_type') == 'inode/directory':
                continue
            if item.get('size_bytes', 0) == 0:
                filepath = Path(item['file'])
                directory = str(filepath.parent) if filepath.parent != Path('.') else '.'
                t = "Scanned" if 'physical_loc' in item else f"Ignored ({item.get('reason', 'Unknown')})"
                zerobyte_txt.append([item['file'], t, directory])
                zerobyte_json.append({
                    "file": item['file'],
                    "type": t,
                    "directory": directory
                })
                
        # Files Larger Than User Threshold (Set to 100 KB)
        THRESHOLD_BYTES = 100 * 1024
        large_files_txt = []
        large_files_json = []
        for item in all_items:
            if item.get('mime_type') == 'inode/directory':
                continue
            size = item.get('size_bytes', 0)
            if size > THRESHOLD_BYTES:
                t = "Scanned" if 'physical_loc' in item else f"Ignored ({item.get('reason', 'Unknown')})"
                large_files_txt.append([item['file'], format_size(size), t])
                large_files_json.append({
                    "file": item['file'],
                    "size_bytes": size,
                    "size_formatted": format_size(size),
                    "type": t
                })
        large_files_txt = sorted(large_files_txt, key=lambda x: x[1], reverse=True)
        large_files_json = sorted(large_files_json, key=lambda x: x['size_bytes'], reverse=True)

        deleted_files_txt = []
        deleted_files_json = []
        if prev_files:
            curr_files_set = {f['file'] for f in self.scanned}
            for path, item in prev_files.items():
                if path not in curr_files_set:
                    size_bytes = item.get('size_bytes', int(item.get('size_kb', 0) * 1024))
                    deleted_files_txt.append([path, item.get('language', 'N/A'), format_size(size_bytes)])
                    deleted_files_json.append({
                        "file": path,
                        "language": item.get('language', 'N/A'),
                        "size_bytes": size_bytes
                    })

        txt = []
        txt.append("=========================================")
        txt.append("          02 FILE METRICS REPORT         ")
        txt.append("=========================================\n")
        
        if prev_files:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append("## Scanned Files Detailed Metrics")
        txt.append(tabulate(rows_txt, headers=headers, tablefmt="grid"))
        
        if prev_files:
            txt.append("\n## Deleted Files Since Last Scan")
            if deleted_files_txt:
                txt.append(tabulate(deleted_files_txt, headers=["File", "Language", "Size"], tablefmt="grid"))
            else:
                txt.append("No files were deleted since the last scan.")
        
        txt.append("\n## Duplicate Files (Identical SHA-256 Hash)")
        if duplicates_txt:
            txt.append(tabulate(duplicates_txt, headers=["SHA-256 (Truncated)", "File", "Size", "Scan Category"], tablefmt="grid"))
        else:
            txt.append("No duplicate files found in this repository.")
            
        txt.append("\n## Zero-byte Files")
        if zerobyte_txt:
            txt.append(tabulate(zerobyte_txt, headers=["File", "Category", "Directory"], tablefmt="grid"))
        else:
            txt.append("No zero-byte files found in this repository.")
            
        txt.append("\n## Files Larger Than 100 KB Threshold")
        if large_files_txt:
            txt.append(tabulate(large_files_txt, headers=["File", "Size", "Category"], tablefmt="grid"))
        else:
            txt.append("No files exceed the 100 KB size threshold.")
            
        json_data = {
            "scanned_files_metrics": rows_json,
            "duplicate_files": duplicates_json,
            "zerobyte_files": zerobyte_json,
            "files_larger_than_threshold": large_files_json
        }
        if prev_files:
            json_data["deleted_files"] = deleted_files_json
            
        self._write_files("02_file_metrics", "\n".join(txt), json_data)

    def _report_03_directory_metrics(self):
        """03 Directory Metrics"""
        dir_data = {}
        for f in self.scanned:
            d = f['directory']
            if d not in dir_data:
                dir_data[d] = {
                    'total_files': 0,
                    'size': 0,
                    'characters': 0,
                    'physical_loc': 0,
                    'logical_loc': 0,
                    'comment_lines': 0,
                    'languages': {},
                    'file_sizes': {}
                }
            dir_data[d]['total_files'] += 1
            dir_data[d]['size'] += f['size_bytes']
            dir_data[d]['characters'] += f.get('char_count', 0)
            dir_data[d]['physical_loc'] += f['physical_loc']
            dir_data[d]['logical_loc'] += f['logical_loc']
            dir_data[d]['comment_lines'] += f['comment_lines']
            dir_data[d]['file_sizes'][f['file']] = f['size_bytes']
            
            lang = f['language']
            dir_data[d]['languages'][lang] = dir_data[d]['languages'].get(lang, 0) + f['physical_loc']
            
        for item in self.ignored:
            filepath = Path(item['file'])
            if item.get('mime_type') == 'inode/directory':
                continue
            d = str(filepath.parent) if filepath.parent != Path('.') else '.'
            if d not in dir_data:
                dir_data[d] = {
                    'total_files': 0,
                    'size': 0,
                    'characters': 0,
                    'physical_loc': 0,
                    'logical_loc': 0,
                    'comment_lines': 0,
                    'languages': {},
                    'file_sizes': {}
                }
            dir_data[d]['total_files'] += 1
            dir_data[d]['size'] += item.get('size_bytes', 0)
            dir_data[d]['file_sizes'][item['file']] = item.get('size_bytes', 0)
            
        rows_json = []
        total_files = self.counts['total_files']
        prev_dirs = self._load_previous_directory_metrics()
        
        for d, metrics in dir_data.items():
            rep_pct = (metrics['total_files'] / total_files * 100) if total_files > 0 else 0.0
            avg_loc = metrics['logical_loc'] / metrics['total_files'] if metrics['total_files'] > 0 else 0.0
            density = (metrics['comment_lines'] / metrics['logical_loc'] * 100) if metrics['logical_loc'] > 0 else 0.0
            
            top_lang = "None"
            if metrics['languages']:
                top_lang = max(metrics['languages'].items(), key=lambda x: x[1])[0]
                
            is_empty = "Yes" if metrics['total_files'] == 0 else "No"
            
            if metrics['file_sizes']:
                largest_f = max(metrics['file_sizes'].items(), key=lambda x: x[1])
                smallest_f = min(metrics['file_sizes'].items(), key=lambda x: x[1])
                largest_val = f"{Path(largest_f[0]).name} ({format_size(largest_f[1])})"
                smallest_val = f"{Path(smallest_f[0]).name} ({format_size(smallest_f[1])})"
            else:
                largest_val = "N/A"
                smallest_val = "N/A"
                
            item_json = {
                "directory": d,
                "total_files": metrics['total_files'],
                "repository_pct": round(rep_pct, 2),
                "size_bytes": metrics['size'],
                "size_formatted": format_size(metrics['size']),
                "characters_count": metrics['characters'],
                "physical_loc": metrics['physical_loc'],
                "logical_loc": metrics['logical_loc'],
                "comment_lines": metrics['comment_lines'],
                "comment_density_pct": round(density, 2),
                "average_loc_per_file": round(avg_loc, 2),
                "top_language": top_lang,
                "empty_directory": is_empty == "Yes",
                "largest_file_val": largest_val,
                "smallest_file_val": smallest_val,
                "largest_file_path": largest_f[0] if metrics['file_sizes'] else "N/A",
                "smallest_file_path": smallest_f[0] if metrics['file_sizes'] else "N/A"
            }
            
            if prev_dirs:
                prev_dir = prev_dirs.get(d)
                if prev_dir:
                    files_change = get_diff_text(metrics['total_files'], prev_dir.get('total_files'))
                    size_change = get_diff_text(metrics['size'], prev_dir.get('size_bytes'), is_bytes=True)
                    loc_change = get_diff_text(metrics['physical_loc'], prev_dir.get('physical_loc'))
                else:
                    files_change = "[NEW]"
                    size_change = "[NEW]"
                    loc_change = "[NEW]"
                item_json["change_since_last_scan"] = {
                    "files_change": files_change,
                    "size_change": size_change,
                    "loc_change": loc_change
                }
                
            rows_json.append(item_json)
            
        rows_json = sorted(rows_json, key=lambda x: x['size_bytes'], reverse=True)
        
        rows_txt = []
        for item in rows_json:
            row = [
                item['directory'],
                item['total_files'],
                f"{item['repository_pct']:.2f}%",
                item['size_formatted'],
                f"{item['characters_count']:,}",
                f"{item['physical_loc']:,}",
                f"{item['logical_loc']:,}",
                f"{item['comment_lines']:,}",
                f"{item['comment_density_pct']:.2f}%",
                f"{item['average_loc_per_file']:.2f}",
                item['top_language'],
                "Yes" if item['empty_directory'] else "No",
                item['largest_file_val'],
                item['smallest_file_val']
            ]
            if prev_dirs:
                chg = item.get("change_since_last_scan", {"files_change": "N/A", "size_change": "N/A", "loc_change": "N/A"})
                row.extend([chg["files_change"], chg["size_change"], chg["loc_change"]])
            rows_txt.append(row)
            
        headers = [
            "Directory", "Total Files", "Repository %", "Size", "Characters",
            "Physical LOC", "Logical LOC", "Comment Lines", 
            "Comment Density", "Average LOC/File", "Top Language",
            "Empty", "Largest File", "Smallest File"
        ]
        if prev_dirs:
            headers.extend(["Files Change", "Size Change", "LOC Change"])
            
        # 1. Directories With Most Nested Levels
        nested_dirs_json = []
        nested_dirs_txt = []
        for item in rows_json:
            d = item['directory']
            depth = len(Path(d).parts) if d != "." else 0
            nested_dirs_json.append({
                "directory": d,
                "depth": depth,
                "total_files": item['total_files']
            })
        nested_dirs_json = sorted(nested_dirs_json, key=lambda x: x['depth'], reverse=True)
        for rank, item in enumerate(nested_dirs_json[:15], 1):
            nested_dirs_txt.append([rank, item['directory'], item['depth'], item['total_files']])
            
        # 2. Directories Containing Only Empty Files
        empty_files_dirs_txt = []
        empty_files_dirs_json = []
        for d, metrics in dir_data.items():
            if metrics['total_files'] > 0 and metrics['size'] == 0:
                empty_files_dirs_txt.append([d, metrics['total_files']])
                empty_files_dirs_json.append({
                    "directory": d,
                    "total_files": metrics['total_files']
                })
        
        txt = []
        txt.append("=========================================")
        txt.append("       03 DIRECTORY METRICS REPORT       ")
        txt.append("=========================================\n")
        
        if prev_dirs:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append("## Folder Traversal Detailed Metrics")
        txt.append(tabulate(rows_txt, headers=headers, tablefmt="grid"))
        
        txt.append("\n## Directories With Most Nested Levels")
        txt.append(tabulate(nested_dirs_txt, headers=["Rank", "Directory", "Nesting Depth", "Total Files"], tablefmt="grid"))
        
        txt.append("\n## Directories Containing Only Empty Files")
        if empty_files_dirs_txt:
            txt.append(tabulate(empty_files_dirs_txt, headers=["Directory", "Total Empty Files"], tablefmt="grid"))
        else:
            txt.append("No directories containing only empty files were found.")
        
        json_data = {
            "directory_metrics": rows_json,
            "nested_depth_directories": nested_dirs_json,
            "empty_files_only_directories": empty_files_dirs_json
        }
        
        self._write_files("03_directory_metrics", "\n".join(txt), json_data)

    def _report_04_language_metrics(self):
        """04 Language Metrics"""
        lang_data = {}
        for f in self.scanned:
            lang = f['language']
            if lang not in lang_data:
                lang_data[lang] = {
                    'files': 0,
                    'size': 0,
                    'characters': 0,
                    'physical_loc': 0,
                    'logical_loc': 0,
                    'comment_lines': 0,
                    'max_loc_single_file': 0
                }
            lang_data[lang]['files'] += 1
            lang_data[lang]['size'] += f['size_bytes']
            lang_data[lang]['characters'] += f.get('char_count', 0)
            lang_data[lang]['physical_loc'] += f['physical_loc']
            lang_data[lang]['logical_loc'] += f['logical_loc']
            lang_data[lang]['comment_lines'] += f['comment_lines']
            lang_data[lang]['max_loc_single_file'] = max(lang_data[lang]['max_loc_single_file'], f['physical_loc'])
            
        rows_json = []
        total_files = self.counts['total_files']
        prev_langs = self._load_previous_language_metrics()
        
        for lang, metrics in lang_data.items():
            pct = (metrics['files'] / total_files * 100) if total_files > 0 else 0.0
            avg_loc = metrics['logical_loc'] / metrics['files'] if metrics['files'] > 0 else 0.0
            density = (metrics['comment_lines'] / metrics['logical_loc'] * 100) if metrics['logical_loc'] > 0 else 0.0
            
            item_json = {
                "language": lang,
                "files": metrics['files'],
                "size_bytes": metrics['size'],
                "size_formatted": format_size(metrics['size']),
                "characters_count": metrics['characters'],
                "physical_loc": metrics['physical_loc'],
                "logical_loc": metrics['logical_loc'],
                "comment_lines": metrics['comment_lines'],
                "comment_density_pct": round(density, 2),
                "percentage": round(pct, 2),
                "average_loc_per_file": round(avg_loc, 2),
                "max_loc_single_file": metrics['max_loc_single_file']
            }
            
            if prev_langs:
                prev_lang = prev_langs.get(lang)
                if prev_lang:
                    files_change = get_diff_text(metrics['files'], prev_lang.get('files'))
                    loc_change = get_diff_text(metrics['physical_loc'], prev_lang.get('physical_loc'))
                    size_change = get_diff_text(metrics['size'], prev_lang.get('size_bytes'), is_bytes=True)
                else:
                    files_change = "[NEW]"
                    loc_change = "[NEW]"
                    size_change = "[NEW]"
                item_json["change_since_last_scan"] = {
                    "files_change": files_change,
                    "loc_change": loc_change,
                    "size_change": size_change
                }
                
            rows_json.append(item_json)
            
        rows_json = sorted(rows_json, key=lambda x: x['physical_loc'], reverse=True)
        
        rows_txt = []
        for item in rows_json:
            row = [
                item['language'],
                item['files'],
                item['size_formatted'],
                f"{item['characters_count']:,}",
                f"{item['physical_loc']:,}",
                f"{item['logical_loc']:,}",
                f"{item['comment_lines']:,}",
                f"{item['comment_density_pct']:.2f}%",
                f"{item['percentage']:.2f}%",
                f"{item['average_loc_per_file']:.2f}",
                f"{item['max_loc_single_file']:,}"
            ]
            if prev_langs:
                chg = item.get("change_since_last_scan", {"files_change": "N/A", "loc_change": "N/A", "size_change": "N/A"})
                row.extend([chg["files_change"], chg["loc_change"], chg["size_change"]])
            rows_txt.append(row)
            
        headers = [
            "Language", "Files", "Size", "Characters", "Physical LOC", "Logical LOC", 
            "Comment Lines", "Comment Density", "Percentage", "Average LOC/File", "Max LOC/File"
        ]
        if prev_langs:
            headers.extend(["Files Change", "LOC Change", "Size Change"])
            
        # Language Version Files Detected
        version_files_detected_txt = []
        version_files_detected_json = []
        all_items = self.scanned + self.ignored
        for item in all_items:
            filename = Path(item['file']).name
            if filename in VERSION_FILES_MAP:
                actual_name, assoc_lang = VERSION_FILES_MAP[filename]
                version_files_detected_txt.append([filename, item['file'], assoc_lang])
                version_files_detected_json.append({
                    "version_file": filename,
                    "detected_path": item['file'],
                    "associated_language": assoc_lang
                })
        
        txt = []
        txt.append("=========================================")
        txt.append("        04 LANGUAGE METRICS REPORT       ")
        txt.append("=========================================\n")
        
        if prev_langs:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append("## Language Statistical Breakdowns")
        txt.append(tabulate(rows_txt, headers=headers, tablefmt="grid"))
        
        txt.append("\n## Language Version / Dependency Manifest Files Detected")
        if version_files_detected_txt:
            txt.append(tabulate(version_files_detected_txt, headers=["Manifest File", "Detected Path", "Associated Ecosystem / Language"], tablefmt="grid"))
        else:
            txt.append("No standard dependency manifest or language version files detected in this repository.")
        
        json_data = {
            "language_metrics": rows_json,
            "version_files_detected": version_files_detected_json
        }
        
        self._write_files("04_language_metrics", "\n".join(txt), json_data)

    def _report_05_documentation_metrics(self):
        """05 Documentation Metrics"""
        doc_files_count = 0
        for f in self.scanned:
            if get_extension_category(Path(f['file'])) == 'Documentation':
                doc_files_count += 1
        
        for item in self.ignored:
            if get_extension_category(Path(item['file'])) == 'Documentation':
                doc_files_count += 1
                
        checklist = {
            "README": "No",
            "LICENSE": "No",
            "CHANGELOG": "No",
            "CONTRIBUTING": "No",
            "SECURITY": "No",
            "AUTHORS": "No",
            "CITATION.cff": "No",
            ".gitignore": "No",
            "pyproject.toml": "No",
            "package.json": "No"
        }
        
        try:
            for name in os.listdir(self.root_path):
                name_lower = name.lower()
                for key in checklist.keys():
                    if key.startswith('.'):
                        if name_lower == key:
                            checklist[key] = "Yes"
                    else:
                        if name_lower.startswith(key.lower()):
                            checklist[key] = "Yes"
        except Exception:
            pass
            
        total_comments = sum(f['comment_lines'] for f in self.scanned)
        total_logical = sum(f['logical_loc'] for f in self.scanned)
        overall_density = (total_comments / total_logical * 100) if total_logical > 0 else 0.0
        
        source_files_with_comments = sum(1 for f in self.scanned if f['comment_lines'] > 0 and get_extension_category(Path(f['file'])) == 'Source Code')
        total_source_files = sum(1 for f in self.scanned if get_extension_category(Path(f['file'])) == 'Source Code')
        comment_coverage_pct = (source_files_with_comments / total_source_files * 100) if total_source_files > 0 else 0.0
        
        prev_docs = self._load_previous_documentation_metrics()
        prev_summary = prev_docs.get('repository_summary', {})
        
        summary_headers = ["Metric", "Value"]
        if prev_docs:
            summary_headers.append("Change")
            
        def get_presence_diff(key, current_val):
            if not prev_docs:
                return "N/A"
            prev_presence = prev_summary.get('file_presence', {})
            prev_val = "Yes" if prev_presence.get(key, False) else "No"
            if prev_val != current_val:
                return f"Changed ({prev_val} -> {current_val})"
            return "None"

        summary_data = [
            ["Documentation Files", doc_files_count] + ([get_diff_text(doc_files_count, prev_summary.get('documentation_files_count'))] if prev_docs else []),
            ["Overall Comment Density", f"{overall_density:.2f}%"] + ([get_pct_diff_text(overall_density, prev_summary.get('overall_comment_density_pct'))] if prev_docs else []),
            ["Percentage of Source Files Having Comments", f"{comment_coverage_pct:.2f}%"] + ([get_pct_diff_text(comment_coverage_pct, prev_summary.get('source_files_comment_coverage_pct'))] if prev_docs else [])
        ]
        for key, val in checklist.items():
            summary_data.append([f"{key} Present", val] + ([get_presence_diff(key, val)] if prev_docs else []))
            
        # File-wise Documentation
        file_docs_txt = []
        file_docs_json = []
        
        prev_file_docs = {}
        for item in prev_docs.get('file_documentation', []):
            path = item.get('file')
            if path:
                prev_file_docs[path] = item
                
        file_docs_headers = ["File", "Size", "Logical LOC", "Comment Lines", "Comment Density", "Documentation Status", "Doc Score (0-100)"]
        if prev_file_docs:
            file_docs_headers.extend(["Doc Score Change", "Comments Change"])
            
        for f in self.scanned:
            cat = get_extension_category(Path(f['file']))
            
            if cat == 'Documentation':
                status = "Documentation File"
                score = 100.0
            else:
                density = f['comment_density']
                if density == 0.0:
                    status = "No Comments"
                    score = 0.0
                elif density < 10.0:
                    status = "Sparingly Documented"
                    score = density * 4.0
                elif density < 20.0:
                    status = "Moderately Documented"
                    score = 40.0 + (density - 10.0) * 3.0
                else:
                    status = "Well Documented"
                    score = min(100.0, 70.0 + (density - 20.0) * 1.5)
                    
            size_kb = f['size_bytes'] / 1024.0
            
            row = [
                f['file'],
                f"{size_kb:.2f} KB",
                f"{f['logical_loc']:,}",
                f"{f['comment_lines']:,}",
                f"{f['comment_density']:.2f}%",
                status,
                f"{score:.1f}"
            ]
            
            item_json = {
                "file": f['file'],
                "size_kb": round(size_kb, 2),
                "logical_loc": f['logical_loc'],
                "comment_lines": f['comment_lines'],
                "comment_density_pct": round(f['comment_density'], 2),
                "documentation_status": status,
                "documentation_score": round(score, 1)
            }
            
            if prev_file_docs:
                prev_f_doc = prev_file_docs.get(f['file'])
                if prev_f_doc:
                    score_change = get_diff_text(score, prev_f_doc.get('documentation_score'))
                    comments_change = get_diff_text(f['comment_lines'], prev_f_doc.get('comment_lines'))
                else:
                    score_change = "[NEW]"
                    comments_change = "[NEW]"
                row.extend([score_change, comments_change])
                item_json["change_since_last_scan"] = {
                    "score_change": score_change,
                    "comments_change": comments_change
                }
                
            file_docs_txt.append(row)
            file_docs_json.append(item_json)
            
        txt = []
        txt.append("=========================================")
        txt.append("     05 DOCUMENTATION METRICS REPORT     ")
        txt.append("=========================================\n")
        
        if prev_docs:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append("## Repository Documentation Summary")
        txt.append(tabulate(summary_data, headers=summary_headers, tablefmt="grid"))
        txt.append("\n## File-wise Documentation Analysis")
        txt.append(tabulate(file_docs_txt, headers=file_docs_headers, tablefmt="grid"))
        
        json_data = {
            "repository_summary": {
                "documentation_files_count": doc_files_count,
                "overall_comment_density_pct": round(overall_density, 2),
                "source_files_comment_coverage_pct": round(comment_coverage_pct, 2),
                "file_presence": {k: v == "Yes" for k, v in checklist.items()}
            },
            "file_documentation": file_docs_json
        }
        
        self._write_files("05_documentation_metrics", "\n".join(txt), json_data)

    def _report_06_extension_statistics(self):
        """06 Extension Statistics"""
        ext_data = {}
        for f in self.scanned:
            ext = f['extension'] or 'no-extension'
            if ext not in ext_data:
                ext_data[ext] = {'files': 0, 'size': 0, 'loc': 0, 'comments': 0, 'logical': 0}
            ext_data[ext]['files'] += 1
            ext_data[ext]['size'] += f['size_bytes']
            ext_data[ext]['loc'] += f['physical_loc']
            ext_data[ext]['comments'] += f['comment_lines']
            ext_data[ext]['logical'] += f['logical_loc']
            
        for item in self.ignored:
            filepath = Path(item['file'])
            ext = filepath.suffix.lower() or 'no-extension'
            if ext not in ext_data:
                ext_data[ext] = {'files': 0, 'size': 0, 'loc': 0, 'comments': 0, 'logical': 0}
            ext_data[ext]['files'] += 1
            ext_data[ext]['size'] += item.get('size_bytes', 0)
            
        total_files = self.counts['total_files']
        prev_exts = self._load_previous_extension_metrics()
        
        extensions_json = []
        for ext, d in ext_data.items():
            pct = (d['files'] / total_files * 100) if total_files > 0 else 0.0
            density = (d['comments'] / d['logical'] * 100) if d['logical'] > 0 else 0.0
            item_json = {
                "extension": ext,
                "files": d['files'],
                "percentage": round(pct, 2),
                "size_bytes": d['size'],
                "size_formatted": format_size(d['size']),
                "total_loc": d['loc'],
                "comment_density_pct": round(density, 2)
            }
            if prev_exts:
                prev_ext = prev_exts.get(ext)
                if prev_ext:
                    files_change = get_diff_text(d['files'], prev_ext.get('files'))
                    size_change = get_diff_text(d['size'], prev_ext.get('size_bytes'), is_bytes=True)
                else:
                    files_change = "[NEW]"
                    size_change = "[NEW]"
                item_json["change_since_last_scan"] = {
                    "files_change": files_change,
                    "size_change": size_change
                }
            extensions_json.append(item_json)
            
        extensions_json_by_files = sorted(extensions_json, key=lambda x: x['files'], reverse=True)
        extensions_json_by_size = sorted(extensions_json, key=lambda x: x['size_bytes'], reverse=True)
        
        ext_headers = ["Extension", "Files", "Percentage", "Size", "Total LOC", "Comment Density"]
        if prev_exts:
            ext_headers.extend(["Files Change", "Size Change"])
            
        ext_txt = []
        for item in extensions_json_by_files:
            row = [
                item['extension'],
                item['files'],
                f"{item['percentage']:.2f}%",
                item['size_formatted'],
                f"{item['total_loc']:,}",
                f"{item['comment_density_pct']:.2f}%"
            ]
            if prev_exts:
                chg = item.get("change_since_last_scan", {"files_change": "N/A", "size_change": "N/A"})
                row.extend([chg["files_change"], chg["size_change"]])
            ext_txt.append(row)
            
        ext_by_size_txt = []
        for item in extensions_json_by_size:
            row = [
                item['extension'],
                item['files'],
                item['size_formatted'],
                f"{item['total_loc']:,}",
                f"{item['comment_density_pct']:.2f}%"
            ]
            if prev_exts:
                chg = item.get("change_since_last_scan", {"files_change": "N/A", "size_change": "N/A"})
                row.extend([chg["files_change"], chg["size_change"]])
            ext_by_size_txt.append(row)
            
        # Unknown Extensions
        unknown_exts_txt = []
        unknown_exts_json = []
        for item in extensions_json:
            ext_name = item['extension']
            cat = get_extension_category(Path(f"test{ext_name}"))
            if cat == 'Others':
                row = [item['extension'], item['files'], f"{item['percentage']:.2f}%"]
                if prev_exts:
                    chg = item.get("change_since_last_scan", {"files_change": "N/A"})
                    row.append(chg["files_change"])
                unknown_exts_txt.append(row)
                unknown_exts_json.append({
                    "extension": item['extension'],
                    "files": item['files'],
                    "percentage": item['percentage']
                })
        unknown_exts_txt = sorted(unknown_exts_txt, key=lambda x: x[1], reverse=True)
        unknown_ext_headers = ["Extension", "Files", "Percentage"]
        if prev_exts:
            unknown_ext_headers.append("Files Change")

        categories = {
            "Source Code": {'files': 0, 'size': 0},
            "Configuration": {'files': 0, 'size': 0},
            "Documentation": {'files': 0, 'size': 0},
            "Assets": {'files': 0, 'size': 0},
            "Others": {'files': 0, 'size': 0}
        }
        for f in self.scanned:
            cat = get_extension_category(Path(f['file']))
            categories[cat]['files'] += 1
            categories[cat]['size'] += f['size_bytes']
        for item in self.ignored:
            cat = get_extension_category(Path(item['file']))
            categories[cat]['files'] += 1
            categories[cat]['size'] += item.get('size_bytes', 0)
            
        categories_data = []
        categories_json = {}
        for cat, val in categories.items():
            pct = (val['files'] / total_files * 100) if total_files > 0 else 0.0
            categories_data.append([
                cat, 
                val['files'], 
                f"{pct:.2f}%", 
                format_size(val['size'])
            ])
            categories_json[cat] = {
                "files": val['files'],
                "percentage": round(pct, 2),
                "size_bytes": val['size'],
                "size_formatted": format_size(val['size'])
            }
            
        txt = []
        txt.append("=========================================")
        txt.append("      06 EXTENSION STATISTICS REPORT     ")
        txt.append("=========================================\n")
        
        if prev_exts:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append("## Extension Breakdown (Sorted by Files)")
        txt.append(tabulate(ext_txt, headers=ext_headers, tablefmt="grid"))
        txt.append("\n## Extensions Sorted By Total Size")
        txt.append(tabulate(ext_by_size_txt, headers=ext_headers, tablefmt="grid"))
        txt.append("\n## Unknown / Uncategorized Extensions")
        if unknown_exts_txt:
            txt.append(tabulate(unknown_exts_txt, headers=unknown_ext_headers, tablefmt="grid"))
        else:
            txt.append("No unknown or uncategorized file extensions were detected.")
        txt.append("\n## Category Summary")
        txt.append(tabulate(categories_data, headers=["Category", "Files", "Percentage", "Scanned Size"], tablefmt="grid"))
        
        json_data = {
            "extensions_by_files": extensions_json_by_files,
            "extensions_by_size": extensions_json_by_size,
            "unknown_extensions": unknown_exts_json,
            "categories": categories_json
        }
        
        self._write_files("06_extension_statistics", "\n".join(txt), json_data)

    def _report_07_size_analysis(self):
        """07 Size Analysis"""
        total_source_size = sum(f['size_bytes'] for f in self.scanned if get_extension_category(Path(f['file'])) == 'Source Code')
        total_source_size += sum(item.get('size_bytes', 0) for item in self.ignored if get_extension_category(Path(item['file'])) == 'Source Code')
        
        overall_size = sum(item.get('size_bytes', 0) for item in (self.scanned + self.ignored))
        total_non_source_size = overall_size - total_source_size
        
        total_scanned_size = sum(f['size_bytes'] for f in self.scanned)
        avg_file_size = total_scanned_size / len(self.scanned) if self.scanned else 0
        
        sizes = sorted([f['size_bytes'] for f in self.scanned])
        n = len(sizes)
        if n == 0:
            median_size = 0
            pct_95_size = 0
        elif n == 1:
            median_size = sizes[0]
            pct_95_size = sizes[0]
        else:
            if n % 2 == 1:
                median_size = sizes[n // 2]
            else:
                median_size = (sizes[n // 2 - 1] + sizes[n // 2]) / 2.0
            pct_95_index = int(0.95 * n)
            pct_95_size = sizes[min(pct_95_index, n - 1)]
            
        prev_size = self._load_previous_size_metrics()
        prev_gen = prev_size.get('general_size_metrics', {})
        
        size_headers = ["Metric", "Value"]
        if prev_size:
            size_headers.append("Change")
            
        general_size_data = [
            ["Total Repository Size", format_size(overall_size)] + ([get_pct_diff_text(overall_size, prev_gen.get('total_repository_size_bytes'), is_bytes=True)] if prev_size else []),
            ["Total Source Code Size", format_size(total_source_size)] + ([get_pct_diff_text(total_source_size, prev_gen.get('total_source_code_size_bytes'), is_bytes=True)] if prev_size else []),
            ["Total Non-Source Size", format_size(total_non_source_size)] + ([get_pct_diff_text(total_non_source_size, prev_gen.get('total_non_source_size_bytes'), is_bytes=True)] if prev_size else []),
            ["Average File Size", format_size(avg_file_size)] + (["N/A"] if prev_size else []),
            ["Median File Size", format_size(median_size)] + (["N/A"] if prev_size else []),
            ["95th Percentile File Size", format_size(pct_95_size)] + (["N/A"] if prev_size else [])
        ]

        # Largest Files (Top 25)
        largest_files = sorted(self.scanned, key=lambda x: x['size_bytes'], reverse=True)[:25]
        largest_files_txt = []
        largest_files_json = []
        for rank, f in enumerate(largest_files, 1):
            largest_files_txt.append([rank, f['file'], format_size(f['size_bytes']), f"{f['physical_loc']:,}"])
            largest_files_json.append({
                "rank": rank,
                "file": f['file'],
                "size_bytes": f['size_bytes'],
                "size_formatted": format_size(f['size_bytes']),
                "physical_loc": f['physical_loc']
            })
            
        # Largest Directories (Top 25)
        dir_sizes = {}
        all_items = self.scanned + self.ignored
        for f in all_items:
            if f.get('mime_type') == 'inode/directory':
                continue
            d = str(Path(f['file']).parent) if Path(f['file']).parent != Path('.') else '.'
            dir_sizes[d] = dir_sizes.get(d, 0) + f.get('size_bytes', 0)
        
        sorted_dirs = sorted(dir_sizes.items(), key=lambda x: x[1], reverse=True)[:25]
        largest_dirs_txt = []
        largest_dirs_json = []
        for rank, (d, size) in enumerate(sorted_dirs, 1):
            largest_dirs_txt.append([rank, d, format_size(size)])
            largest_dirs_json.append({
                "rank": rank,
                "directory": d,
                "size_bytes": size,
                "size_formatted": format_size(size)
            })
            
        # Smallest Files (Top 25)
        smallest_files = sorted([f for f in all_items if f.get('mime_type') != 'inode/directory'], key=lambda x: x.get('size_bytes', 0))[:25]
        smallest_files_txt = []
        smallest_files_json = []
        for rank, f in enumerate(smallest_files, 1):
            smallest_files_txt.append([rank, f['file'], format_size(f.get('size_bytes', 0))])
            smallest_files_json.append({
                "rank": rank,
                "file": f['file'],
                "size_bytes": f.get('size_bytes', 0),
                "size_formatted": format_size(f.get('size_bytes', 0))
            })
            
        # Top 25 Binary Files
        binary_files = [x for x in self.ignored if x.get('reason') == 'Binary File']
        sorted_binary = sorted(binary_files, key=lambda x: x.get('size_bytes', 0), reverse=True)[:25]
        binary_files_txt = []
        binary_files_json = []
        for rank, f in enumerate(sorted_binary, 1):
            binary_files_txt.append([rank, f['file'], format_size(f.get('size_bytes', 0)), f.get('mime_type', 'Unknown')])
            binary_files_json.append({
                "rank": rank,
                "file": f['file'],
                "size_bytes": f.get('size_bytes', 0),
                "size_formatted": format_size(f.get('size_bytes', 0)),
                "mime_type": f.get('mime_type', 'Unknown')
            })
            
        # Top 25 Documentation Files
        doc_files = [x for x in all_items if get_extension_category(Path(x['file'])) == 'Documentation' and x.get('mime_type') != 'inode/directory']
        sorted_doc = sorted(doc_files, key=lambda x: x.get('size_bytes', 0), reverse=True)[:25]
        doc_files_txt = []
        doc_files_json = []
        for rank, f in enumerate(sorted_doc, 1):
            loc_val = f.get('physical_loc', 'N/A')
            doc_files_txt.append([rank, f['file'], format_size(f.get('size_bytes', 0)), loc_val])
            doc_files_json.append({
                "rank": rank,
                "file": f['file'],
                "size_bytes": f.get('size_bytes', 0),
                "size_formatted": format_size(f.get('size_bytes', 0)),
                "physical_loc": loc_val
            })

        # File Size Distribution
        distribution = {
            "0-1 KB": 0,
            "1-5 KB": 0,
            "5-10 KB": 0,
            "10-50 KB": 0,
            "50-100 KB": 0,
            "100-500 KB": 0,
            "500 KB-1 MB": 0,
            "1 MB+": 0
        }
        for f in all_items:
            if f.get('mime_type') == 'inode/directory':
                continue
            kb = f.get('size_bytes', 0) / 1024.0
            if kb <= 1.0:
                distribution["0-1 KB"] += 1
            elif kb <= 5.0:
                distribution["1-5 KB"] += 1
            elif kb <= 10.0:
                distribution["5-10 KB"] += 1
            elif kb <= 50.0:
                distribution["10-50 KB"] += 1
            elif kb <= 100.0:
                distribution["50-100 KB"] += 1
            elif kb <= 500.0:
                distribution["100-500 KB"] += 1
            elif kb <= 1024.0:
                distribution["500 KB-1 MB"] += 1
            else:
                distribution["1 MB+"] += 1
                
        dist_data = [[k, v] for k, v in distribution.items()]
        
        txt = []
        txt.append("=========================================")
        txt.append("          07 SIZE ANALYSIS REPORT        ")
        txt.append("=========================================\n")
        
        if prev_size:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append("## General Size Metrics")
        txt.append(tabulate(general_size_data, headers=size_headers, tablefmt="grid"))
        txt.append("\n## Largest Scanned Files (Top 25)")
        txt.append(tabulate(largest_files_txt, headers=["Rank", "File", "Size", "Physical LOC"], tablefmt="grid"))
        txt.append("\n## Largest Directories (Top 25)")
        txt.append(tabulate(largest_dirs_txt, headers=["Rank", "Directory", "Size"], tablefmt="grid"))
        txt.append("\n## Smallest Files (Top 25)")
        txt.append(tabulate(smallest_files_txt, headers=["Rank", "File", "Size"], tablefmt="grid"))
        txt.append("\n## Largest Binary Files (Top 25)")
        if binary_files_txt:
            txt.append(tabulate(binary_files_txt, headers=["Rank", "File", "Size", "MIME Type"], tablefmt="grid"))
        else:
            txt.append("No binary files detected in this repository.")
        txt.append("\n## Largest Documentation Files (Top 25)")
        if doc_files_txt:
            txt.append(tabulate(doc_files_txt, headers=["Rank", "File", "Size", "Physical LOC"], tablefmt="grid"))
        else:
            txt.append("No documentation files detected in this repository.")
        txt.append("\n## File Size Distribution")
        txt.append(tabulate(dist_data, headers=["Size Range", "Files"], tablefmt="grid"))
        
        json_data = {
            "general_size_metrics": {
                "total_repository_size_bytes": overall_size,
                "total_repository_size_formatted": format_size(overall_size),
                "total_source_code_size_bytes": total_source_size,
                "total_source_code_size_formatted": format_size(total_source_size),
                "total_non_source_size_bytes": total_non_source_size,
                "total_non_source_size_formatted": format_size(total_non_source_size),
                "average_file_size_formatted": format_size(avg_file_size),
                "median_file_size_formatted": format_size(median_size),
                "95_percentile_file_size_formatted": format_size(pct_95_size)
            },
            "largest_files": largest_files_json,
            "largest_directories": largest_dirs_json,
            "smallest_files": smallest_files_json,
            "largest_binary_files": binary_files_json,
            "largest_documentation_files": doc_files_json,
            "file_size_distribution": distribution
        }
        
        self._write_files("07_size_analysis", "\n".join(txt), json_data)

    def _report_08_project_structure(self):
        """08 Project Structure"""
        dirs_visited = self.results['dirs_visited']
        total_dirs = len(dirs_visited) + 1
        total_files = self.counts['total_files']
        ratio = total_files / total_dirs if total_dirs > 0 else 0
        
        max_depth = 0
        depths_sum = 0
        for d in dirs_visited:
            rel_parts = d.relative_to(self.root_path).parts
            depth = len(rel_parts)
            depths_sum += depth
            max_depth = max(max_depth, depth)
            
        avg_depth = depths_sum / total_dirs if total_dirs > 0 else 0
        
        dir_files_count = {}
        all_items = self.scanned + self.ignored
        for f in all_items:
            if f.get('mime_type') == 'inode/directory':
                continue
            d = str(Path(f['file']).parent) if Path(f['file']).parent != Path('.') else '.'
            dir_files_count[d] = dir_files_count.get(d, 0) + 1
            
        if dir_files_count:
            widest_d, widest_count = max(dir_files_count.items(), key=lambda x: x[1])
            widest_dir_val = f"{widest_d} ({widest_count} files)"
        else:
            widest_dir_val = "N/A"
            
        prev_struct = self._load_previous_structure_metrics()
        prev_over = prev_struct.get('structural_overview', {})
        
        struct_headers = ["Metric", "Value"]
        if prev_struct:
            struct_headers.append("Change")
            
        structure_summary = [
            ["Total Directories Traversed", total_dirs] + ([get_diff_text(total_dirs, prev_over.get('total_directories_traversed'))] if prev_struct else []),
            ["File-to-Folder Ratio", f"{ratio:.2f} files/dir"] + ([get_pct_diff_text(ratio, prev_over.get('file_to_folder_ratio'))] if prev_struct else []),
            ["Maximum Nesting Depth", max_depth] + ([get_diff_text(max_depth, prev_over.get('maximum_nesting_depth'))] if prev_struct else []),
            ["Average Directory Depth", f"{avg_depth:.2f}"] + ([get_pct_diff_text(avg_depth, prev_over.get('average_directory_depth'))] if prev_struct else []),
            ["Average Files Per Directory", f"{ratio:.2f}"] + ([get_pct_diff_text(ratio, prev_over.get('average_files_per_directory'))] if prev_struct else []),
            ["Widest Directory (Max Files)", widest_dir_val] + (["N/A"] if prev_struct else [])
        ]

        # Top Level Directories
        top_dirs = {}
        for f in self.scanned:
            p = Path(f['file'])
            parts = p.parts
            if len(parts) > 1:
                top_d = parts[0]
            else:
                top_d = "."
            top_dirs[top_d] = top_dirs.get(top_d, 0) + 1
        top_dirs_data = sorted([[k, v] for k, v in top_dirs.items()], key=lambda x: x[1], reverse=True)
        
        # Folder Depths
        depths = {0: 1}
        for d in dirs_visited:
            rel_parts = d.relative_to(self.root_path).parts
            depth = len(rel_parts)
            depths[depth] = depths.get(depth, 0) + 1
        depths_data = sorted([[k, v] for k, v in depths.items()])
        
        # Deepest Directories (Top 20)
        dir_depths = [{"directory": ".", "depth": 0}]
        for d in dirs_visited:
            rel_parts = d.relative_to(self.root_path).parts
            dir_depths.append({
                "directory": str(d.relative_to(self.root_path)),
                "depth": len(rel_parts)
            })
        dir_depths_sorted = sorted(dir_depths, key=lambda x: x['depth'], reverse=True)[:20]
        deepest_dirs_txt = [[item['directory'], item['depth']] for item in dir_depths_sorted]
        
        # Project Composition
        categories = {
            "Source Code": 0,
            "Configuration": 0,
            "Documentation": 0,
            "Assets": 0,
            "Others": 0
        }
        for f in self.scanned:
            cat = get_extension_category(Path(f['file']))
            categories[cat] += 1
        for item in self.ignored:
            cat = get_extension_category(Path(item['file']))
            categories[cat] += 1
        composition_data = [[k, v] for k, v in categories.items()]
        
        # Directory Tree Summary Table
        tree_sum_data = [
            ["Root Folder", self.root_path.name],
            ["Total Visited Subdirectories", len(dirs_visited)],
            ["Total Scanned Files", len(self.scanned)],
            ["Total Ignored Files", len(self.ignored)]
        ]
        
        # Files By Depth Table
        files_by_depth = {}
        for f in all_items:
            if f.get('mime_type') == 'inode/directory':
                continue
            p = Path(f['file'])
            depth = len(p.parent.parts) if p.parent != Path('.') else 0
            files_by_depth[depth] = files_by_depth.get(depth, 0) + 1
        files_by_depth_data = sorted([[k, v] for k, v in files_by_depth.items()])
        
        # ASCII directory tree
        tree_lines = [self.root_path.name]
        tree_lines.extend(generate_ascii_tree(self.root_path, max_depth=5))
        tree_txt = "\n".join(tree_lines)
        
        txt = []
        txt.append("=========================================")
        txt.append("        08 PROJECT STRUCTURE REPORT      ")
        txt.append("=========================================\n")
        
        if prev_struct:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append("## Structural Overview")
        txt.append(tabulate(structure_summary, headers=struct_headers, tablefmt="grid"))
        txt.append("\n## Directory Tree Summary")
        txt.append(tabulate(tree_sum_data, headers=["Structure Parameter", "Value"], tablefmt="grid"))
        txt.append("\n## Top Level Directories")
        txt.append(tabulate(top_dirs_data, headers=["Directory", "Files"], tablefmt="grid"))
        txt.append("\n## Folder Depth Distribution")
        txt.append(tabulate(depths_data, headers=["Depth", "Directories"], tablefmt="grid"))
        txt.append("\n## Files Distribution By Depth")
        txt.append(tabulate(files_by_depth_data, headers=["Nesting Depth", "Files Count"], tablefmt="grid"))
        txt.append("\n## Deepest Directories (Top 20)")
        txt.append(tabulate(deepest_dirs_txt, headers=["Directory", "Depth"], tablefmt="grid"))
        txt.append("\n## Project Composition")
        txt.append(tabulate(composition_data, headers=["Category", "Files"], tablefmt="grid"))
        txt.append("\n## Visual Repository Directory Tree (Depth Limit: 5)")
        txt.append("```\n" + tree_txt + "\n```")
        
        json_data = {
            "structural_overview": {
                "total_directories_traversed": total_dirs,
                "file_to_folder_ratio": round(ratio, 2),
                "maximum_nesting_depth": max_depth,
                "average_directory_depth": round(avg_depth, 2),
                "widest_directory": widest_dir_val
            },
            "directory_tree_summary": {
                "root_folder": self.root_path.name,
                "visited_subdirectories_count": len(dirs_visited),
                "total_scanned_files": len(self.scanned),
                "total_ignored_files": len(self.ignored)
            },
            "top_level_directories": [{"directory": k, "files": v} for k, v in top_dirs_data],
            "folder_depths": [{"depth": k, "directories": v} for k, v in depths_data],
            "files_by_depth": [{"depth": k, "files": v} for k, v in files_by_depth_data],
            "deepest_directories": dir_depths_sorted,
            "project_composition": categories,
            "directory_tree_list": tree_lines
        }
        
        self._write_files("08_project_structure", "\n".join(txt), json_data)

    def _report_09_scan_statistics(self):
        """09 Scan Statistics"""
        total_scanned_size = sum(f['size_bytes'] for f in self.scanned)
        total_phys_loc = sum(f['physical_loc'] for f in self.scanned)
        total_chars = sum(f.get('char_count', 0) for f in self.scanned)
        
        scanned_count = self.counts['supported_files']
        files_speed = scanned_count / self.scan_duration if self.scan_duration > 0 else 0.0
        lines_speed = total_phys_loc / self.scan_duration if self.scan_duration > 0 else 0.0
        size_speed_kb = (total_scanned_size / 1024.0) / self.scan_duration if self.scan_duration > 0 else 0.0
        
        try:
            p = psutil.Process()
            mem = p.memory_info()
            peak_mem = getattr(mem, 'peak_wset', mem.rss)
            peak_memory_formatted = format_size(peak_mem)
        except Exception:
            peak_mem = 0
            peak_memory_formatted = "N/A"
            
        avg_processing_time = self.scan_duration / scanned_count if scanned_count > 0 else 0.0
        skipped_due_to_errors = sum(1 for item in self.ignored if item['reason'].startswith('Error during analysis'))
        
        prev_stats = self._load_previous_scan_stats()
        prev_sum = prev_stats.get('summary', {})
        
        stats_headers = ["Metric", "Value"]
        if prev_stats:
            stats_headers.append("Change")
            
        summary_data = [
            ["Files Scanned (Supported)", scanned_count] + ([get_diff_text(scanned_count, prev_sum.get('files_scanned'))] if prev_stats else []),
            ["Files Ignored (Total)", self.counts['ignored_files']] + ([get_diff_text(self.counts['ignored_files'], prev_sum.get('files_ignored'))] if prev_stats else []),
            ["Binary Files Ignored", self.counts['binary_files']] + ([get_diff_text(self.counts['binary_files'], prev_sum.get('binary_files'))] if prev_stats else []),
            ["Unsupported Files Ignored", self.counts['unsupported_files']] + ([get_diff_text(self.counts['unsupported_files'], prev_sum.get('unsupported_files'))] if prev_stats else []),
            ["Hidden Files Ignored", self.counts['hidden_files']] + ([get_diff_text(self.counts['hidden_files'], prev_sum.get('hidden_files'))] if prev_stats else []),
            ["Total Characters Processed", f"{total_chars:,}"] + ([get_pct_diff_text(total_chars, prev_sum.get('total_characters_processed'))] if prev_stats else []),
            ["Scan Duration", f"{self.scan_duration:.4f} seconds"] + ([f"{self.scan_duration - prev_sum.get('scan_duration_seconds', 0):+.4f} s"] if prev_stats else []),
            ["Average Processing Time/File", f"{avg_processing_time * 1000:.3f} ms"] + ([f"{(avg_processing_time - prev_sum.get('average_processing_time_seconds', 0)) * 1000:+.3f} ms"] if prev_stats else []),
            ["Peak Memory Usage", peak_memory_formatted] + (["N/A"] if prev_stats else []),
            ["Files Skipped Due To Errors", skipped_due_to_errors] + ([get_diff_text(skipped_due_to_errors, prev_sum.get('files_skipped_due_to_errors'))] if prev_stats else []),
            ["Scan Completion Percentage", "100.00%"] + (["0.00%"] if prev_stats else []),
            ["Scan Processing Speed (Files)", f"{files_speed:.2f} files/sec"] + (["N/A"] if prev_stats else []),
            ["Scan Processing Speed (LOC)", f"{lines_speed:.2f} lines/sec"] + (["N/A"] if prev_stats else []),
            ["Scan Processing Speed (KB)", f"{size_speed_kb:.2f} KB/sec"] + (["N/A"] if prev_stats else []),
            ["Warnings Logged", len(self.warnings)] + ([get_diff_text(len(self.warnings), prev_sum.get('warnings_count'))] if prev_stats else []),
            ["Errors Logged", len(self.errors)] + ([get_diff_text(len(self.errors), prev_sum.get('errors_count'))] if prev_stats else [])
        ]
        
        ignored_folders_list = []
        for item in self.ignored:
            if item['reason'] == 'Ignored Folder':
                ignored_folders_list.append([item['file']])
        ignored_folders_list = sorted(list({x[0] for x in ignored_folders_list}))
        ignored_folders_table = [[x] for x in ignored_folders_list]

        ignored_txt = []
        ignored_json = []
        for item in self.ignored:
            ignored_json.append({
                "file": item['file'],
                "reason": item['reason']
            })
        for item in self.ignored[:150]:
            ignored_txt.append([item['file'], item['reason']])
            
        warnings_table = [[item['file'], item['message']] for item in self.warnings]
        errors_table = [[item['directory'], item['message']] for item in self.errors]
            
        txt = []
        txt.append("=========================================")
        txt.append("        09 SCAN STATISTICS REPORT        ")
        txt.append("=========================================\n")
        
        if prev_stats:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append("## Traversal Summary")
        txt.append(tabulate(summary_data, headers=stats_headers, tablefmt="grid"))
        
        if ignored_folders_table:
            txt.append("\n## Ignored Directories Excluded")
            txt.append(tabulate(ignored_folders_table, headers=["Directory Path"], tablefmt="grid"))
        txt.append(f"\n## Ignored/Skipped Files (Showing top {len(ignored_txt)} of {len(ignored_json)})")
        txt.append(tabulate(ignored_txt, headers=["File", "Reason"], tablefmt="grid"))
        if warnings_table:
            txt.append("\n## Scan Warnings")
            txt.append(tabulate(warnings_table, headers=["File", "Warning Message"], tablefmt="grid"))
        if errors_table:
            txt.append("\n## Scan Directory Errors")
            txt.append(tabulate(errors_table, headers=["Directory", "Error Message"], tablefmt="grid"))
        
        json_data = {
            "summary": {
                "files_scanned": scanned_count,
                "files_ignored": self.counts['ignored_files'],
                "binary_files": self.counts['binary_files'],
                "unsupported_files": self.counts['unsupported_files'],
                "hidden_files": self.counts['hidden_files'],
                "total_characters_processed": total_chars,
                "scan_duration_seconds": self.scan_duration,
                "average_processing_time_seconds": avg_processing_time,
                "peak_memory_usage": peak_memory_formatted,
                "files_skipped_due_to_errors": skipped_due_to_errors,
                "scan_completion_pct": 100.00,
                "scan_speed_files_per_sec": files_speed,
                "scan_speed_lines_per_sec": lines_speed,
                "scan_speed_kb_per_sec": size_speed_kb,
                "warnings_count": len(self.warnings),
                "errors_count": len(self.errors)
            },
            "ignored_directories": ignored_folders_list,
            "ignored_files": ignored_json,
            "warnings": self.warnings,
            "errors": self.errors
        }
        
        self._write_files("09_scan_statistics", "\n".join(txt), json_data)

    def _report_10_metadata(self):
        """10 Metadata"""
        local_time = time.localtime(self.results.get('start_time', time.time()))
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
        
        try:
            import git
            repo = git.Repo(self.root_path, search_parent_directories=True)
            is_git = "Yes"
            git_branch = repo.active_branch.name
            git_commit = repo.head.commit.hexsha
        except Exception:
            is_git = "No"
            git_branch = "N/A"
            git_commit = "N/A"
            
        tz_name = time.tzname[0] if time.tzname else "UTC"
        hostname = platform.node()
        username = getpass.getuser()

        prev_meta = self._load_previous_metadata()
        
        env_headers = ["Property", "Value"]
        if prev_meta:
            env_headers.append("Change")
            
        env_data = [
            ["Archon One Version", "0.2.0"] + (["None"] if prev_meta else []),
            ["Python Version", sys.version.split()[0]] + (["None"] if prev_meta else []),
            ["Python Implementation", platform.python_implementation()] + (["None"] if prev_meta else []),
            ["Python Compiler", platform.python_compiler()] + (["None"] if prev_meta else []),
            ["Operating System", f"{platform.system()} {platform.release()} ({os.name})"] + (["None"] if prev_meta else []),
            ["CPU Architecture", platform.machine()] + (["None"] if prev_meta else []),
            ["System Processor", platform.processor() or "N/A"] + (["None"] if prev_meta else []),
            ["Hostname", hostname] + (["None"] if prev_meta else []),
            ["Username", username] + (["None"] if prev_meta else []),
            ["Current Working Directory", os.getcwd()] + (["None"] if prev_meta else []),
            ["Local Time Zone", tz_name] + (["None"] if prev_meta else []),
            ["Timestamp", timestamp_str] + ([f"Since {prev_meta.get('environment', {}).get('timestamp', 'N/A')}"] if prev_meta else [])
        ]
        
        git_headers = ["Git Property", "Value"]
        if prev_meta:
            git_headers.append("Change")
            
        prev_git = prev_meta.get('git_control', {})
        def get_git_diff(key, curr_val):
            if not prev_meta:
                return "N/A"
            prev_val = prev_git.get(key, "N/A")
            if str(prev_val) != str(curr_val):
                return f"Changed ({prev_val} -> {curr_val})"
            return "None"

        git_data = [
            ["Repository Is Git Controlled", is_git] + ([get_git_diff('is_git_controlled', is_git == "Yes")] if prev_meta else []),
            ["Current Git Branch", git_branch] + ([get_git_diff('current_git_branch', git_branch)] if prev_meta else []),
            ["Current Commit Hash", git_commit] + ([get_git_diff('current_commit_hash', git_commit)] if prev_meta else [])
        ]
        
        from archon.core.parser import EXTENSION_TO_LANGUAGE
        supported_langs = sorted(list(set(EXTENSION_TO_LANGUAGE.values())))
        supported_extensions = sorted(list(EXTENSION_TO_LANGUAGE.keys()))
        
        config_data = [
            ["Supported Languages Count", len(supported_langs)],
            ["Supported Extensions Count", len(supported_extensions)],
            ["Supported Languages List", ", ".join(supported_langs)],
            ["Supported Extensions List", ", ".join(supported_extensions)],
            ["Ignore Binary Files", "Yes"],
            ["Ignore Hidden Files", "Yes"],
            ["Ignore Build Folders", "Yes"],
            ["Ignored Folder Names Set", ", ".join(sorted(list(IGNORED_FOLDERS)))],
            ["Enabled Modules", "01_Code_Metrics, 11_Dependencies"]
        ]
        
        txt = []
        txt.append("=========================================")
        txt.append("            10 METADATA REPORT           ")
        txt.append("=========================================\n")
        
        if prev_meta:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append("## Environment Details")
        txt.append(tabulate(env_data, headers=env_headers, tablefmt="grid"))
        txt.append("\n## Git Control Details")
        txt.append(tabulate(git_data, headers=git_headers, tablefmt="grid"))
        txt.append("\n## Configuration Details")
        txt.append(tabulate(config_data, headers=["Setting", "Value"], tablefmt="grid"))
        
        json_data = {
            "environment": {
                "archon_one_version": "0.2.0",
                "python_version": sys.version,
                "python_implementation": platform.python_implementation(),
                "python_compiler": platform.python_compiler(),
                "operating_system": f"{platform.system()} {platform.release()}",
                "os_name": os.name,
                "cpu_architecture": platform.machine(),
                "processor": platform.processor(),
                "hostname": hostname,
                "username": username,
                "current_working_directory": os.getcwd(),
                "local_timezone": tz_name,
                "timestamp": timestamp_str
            },
            "git_control": {
                "is_git_controlled": is_git == "Yes",
                "current_git_branch": git_branch,
                "current_commit_hash": git_commit
            },
            "configuration": {
                "supported_languages_list": supported_langs,
                "supported_extensions_list": supported_extensions,
                "ignore_binary_files": True,
                "ignore_hidden_files": True,
                "ignore_build_folders": True,
                "ignored_folder_names": sorted(list(IGNORED_FOLDERS)),
                "enabled_modules": ["01_Code_Metrics", "11_Dependencies"]
            }
        }
        
        self._write_files("10_metadata", "\n".join(txt), json_data)

    def _report_11_dependencies(self):
        """11 Dependencies Report"""
        dependencies = self._extract_dependencies()
        prev_deps_data = self._load_previous_dependencies()
        prev_list = prev_deps_data.get('dependencies_list', [])
        
        # Build map of previous dependencies
        prev_deps = {}
        for item in prev_list:
            package = item.get('package')
            if package:
                prev_deps[package] = item
                
        # Summary calculations
        ecosystems = {}
        manifests = set()
        prod_count = 0
        dev_count = 0
        
        for dep in dependencies:
            eco = dep['ecosystem']
            ecosystems[eco] = ecosystems.get(eco, 0) + 1
            manifests.add(dep['file'])
            if "Development" in dep['type']:
                dev_count += 1
            else:
                prod_count += 1
                
        summary_headers = ["Metric / Ecosystem", "Count / Value"]
        if prev_deps_data:
            summary_headers.append("Change")
            
        prev_sum = prev_deps_data.get('dependencies_summary', {})
        summary_data = []
        for eco, count in ecosystems.items():
            prev_breakdown = prev_sum.get('ecosystems_breakdown', {})
            summary_data.append([eco, count] + ([get_diff_text(count, prev_breakdown.get(eco, 0))] if prev_deps_data else []))
            
        summary_data.append(["Total Dependencies", len(dependencies)] + ([get_diff_text(len(dependencies), prev_sum.get('total_dependencies'))] if prev_deps_data else []))
        summary_data.append(["Production Dependencies", prod_count] + ([get_diff_text(prod_count, prev_sum.get('production_dependencies'))] if prev_deps_data else []))
        summary_data.append(["Development Dependencies", dev_count] + ([get_diff_text(dev_count, prev_sum.get('development_dependencies'))] if prev_deps_data else []))
        summary_data.append(["Manifest Files Detected", len(manifests)] + ([get_diff_text(len(manifests), prev_sum.get('manifest_files_count'))] if prev_deps_data else []))
        
        # Details list
        rows_txt = []
        rows_json = []
        
        details_headers = ["Package", "Version Constraint", "Ecosystem", "Type", "Defined In"]
        if prev_deps:
            details_headers.append("Version Constraint Change")
            
        for dep in dependencies:
            row = [
                dep['package'],
                dep['version'],
                dep['ecosystem'],
                dep['type'],
                dep['file']
            ]
            item_json = {
                "package": dep['package'],
                "version_constraint": dep['version'],
                "ecosystem": dep['ecosystem'],
                "dependency_type": dep['type'],
                "defined_in": dep['file']
            }
            if prev_deps:
                prev_dep = prev_deps.get(dep['package'])
                if prev_dep:
                    prev_version = prev_dep.get('version_constraint', 'any')
                    if prev_version != dep['version']:
                        ver_change = f"Changed ({prev_version} -> {dep['version']})"
                    else:
                        ver_change = "None"
                else:
                    ver_change = "[NEW]"
                row.append(ver_change)
                item_json["change_since_last_scan"] = {
                    "version_constraint_change": ver_change
                }
            rows_txt.append(row)
            rows_json.append(item_json)
            
        rows_txt = sorted(rows_txt, key=lambda x: x[0].lower())
        rows_json = sorted(rows_json, key=lambda x: x['package'].lower())
        
        # Deleted Dependencies
        deleted_deps_txt = []
        deleted_deps_json = []
        if prev_deps:
            curr_deps_set = {d['package'] for d in dependencies}
            for pkg, item in prev_deps.items():
                if pkg not in curr_deps_set:
                    deleted_deps_txt.append([pkg, item.get('version_constraint', 'any'), item.get('ecosystem', 'N/A'), item.get('defined_in', 'N/A')])
                    deleted_deps_json.append({
                        "package": pkg,
                        "version_constraint": item.get('version_constraint', 'any'),
                        "ecosystem": item.get('ecosystem', 'N/A'),
                        "defined_in": item.get('defined_in', 'N/A')
                    })
        deleted_deps_txt = sorted(deleted_deps_txt, key=lambda x: x[0].lower())
        
        txt = []
        txt.append("=========================================")
        txt.append("         11 DEPENDENCIES REPORT          ")
        txt.append("=========================================\n")
        
        if prev_deps_data:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append("## Dependencies Summary")
        txt.append(tabulate(summary_data, headers=summary_headers, tablefmt="grid"))
        txt.append("\n## Detailed Dependencies List")
        if rows_txt:
            txt.append(tabulate(rows_txt, headers=details_headers, tablefmt="grid"))
        else:
            txt.append("No third-party package dependencies were detected in this repository.")
            
        if prev_deps:
            txt.append("\n## Deleted Dependencies Since Last Scan")
            if deleted_deps_txt:
                txt.append(tabulate(deleted_deps_txt, headers=["Package", "Version Constraint", "Ecosystem", "Defined In"], tablefmt="grid"))
            else:
                txt.append("No dependencies were deleted since the last scan.")
                
        json_data = {
            "dependencies_summary": {
                "total_dependencies": len(dependencies),
                "production_dependencies": prod_count,
                "development_dependencies": dev_count,
                "manifest_files_count": len(manifests),
                "ecosystems_breakdown": ecosystems,
                "manifest_files_list": sorted(list(manifests))
            },
            "dependencies_list": rows_json
        }
        if prev_deps:
            json_data["deleted_dependencies"] = deleted_deps_json
            
        self._write_files("11_dependencies", "\n".join(txt), json_data)

    def _extract_dependencies(self) -> List[Dict[str, Any]]:
        dependencies = []
        all_items = self.scanned + self.ignored
        
        for item in all_items:
            rel_path = item['file']
            filepath = self.root_path / rel_path
            if not filepath.is_file():
                continue
                
            name = filepath.name
            
            try:
                content = filepath.read_text(encoding='utf-8')
            except Exception:
                try:
                    content = filepath.read_text(encoding='latin-1')
                except Exception:
                    continue
                    
            if name == "package.json":
                try:
                    data = json.loads(content)
                    for key, dep_type in [("dependencies", "Production"), ("devDependencies", "Development"), ("peerDependencies", "Peer")]:
                        deps = data.get(key, {})
                        for dep_name, constraint in deps.items():
                            dependencies.append({
                                "package": dep_name,
                                "version": constraint,
                                "ecosystem": "npm",
                                "type": dep_type,
                                "file": rel_path
                            })
                except Exception:
                    pass
            elif name == "requirements.txt":
                import re
                for line in content.splitlines():
                    line = line.strip()
                    if not line or line.startswith('#') or line.startswith('-r') or line.startswith('-e'):
                        continue
                    match = re.match(r'^([a-zA-Z0-9_\-\.]+)(.*)$', line)
                    if match:
                        dep_name, constraint = match.groups()
                        dependencies.append({
                            "package": dep_name.strip(),
                            "version": constraint.strip() or "any",
                            "ecosystem": "Python (pip)",
                            "type": "Production",
                            "file": rel_path
                        })
            elif name == "pyproject.toml":
                import tomllib
                import re
                try:
                    data = tomllib.loads(content)
                    deps = data.get("project", {}).get("dependencies", [])
                    for dep in deps:
                        match = re.match(r'^([a-zA-Z0-9_\-\.]+)(.*)$', dep.strip())
                        if match:
                            dep_name, constraint = match.groups()
                            dependencies.append({
                                "package": dep_name.strip(),
                                "version": constraint.strip() or "any",
                                "ecosystem": "Python (setuptools/poetry)",
                                "type": "Production",
                                "file": rel_path
                            })
                    opt_deps = data.get("project", {}).get("optional-dependencies", {})
                    for group, deps_list in opt_deps.items():
                        for dep in deps_list:
                            match = re.match(r'^([a-zA-Z0-9_\-\.]+)(.*)$', dep.strip())
                            if match:
                                dep_name, constraint = match.groups()
                                dependencies.append({
                                    "package": dep_name.strip(),
                                    "version": constraint.strip() or "any",
                                    "ecosystem": "Python (setuptools/poetry)",
                                    "type": f"Development ({group})",
                                    "file": rel_path
                                })
                except Exception:
                    pass
            elif name == "pubspec.yaml":
                in_deps = False
                in_dev_deps = False
                for line in content.splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith('#'):
                        continue
                    if line.startswith('dependencies:'):
                        in_deps = True
                        in_dev_deps = False
                        continue
                    elif line.startswith('dev_dependencies:'):
                        in_deps = False
                        in_dev_deps = True
                        continue
                    elif line and not line.startswith(' ') and not line.startswith('\t'):
                        in_deps = False
                        in_dev_deps = False
                        
                    if in_deps or in_dev_deps:
                        if ':' in stripped:
                            dep_name, constraint = stripped.split(':', 1)
                            dep_name = dep_name.strip()
                            constraint = constraint.strip()
                            if constraint and not constraint.startswith('{'):
                                dependencies.append({
                                    "package": dep_name,
                                    "version": constraint,
                                    "ecosystem": "Dart/Flutter",
                                    "type": "Production" if in_deps else "Development",
                                    "file": rel_path
                                })
            elif name == "Cargo.toml":
                import tomllib
                try:
                    data = tomllib.loads(content)
                    for key, dep_type in [("dependencies", "Production"), ("dev-dependencies", "Development")]:
                        deps = data.get(key, {})
                        for dep_name, constraint in deps.items():
                            if isinstance(constraint, dict):
                                version = constraint.get("version", "custom")
                            else:
                                version = str(constraint)
                            dependencies.append({
                                "package": dep_name,
                                "version": version,
                                "ecosystem": "Cargo",
                                "type": dep_type,
                                "file": rel_path
                            })
                except Exception:
                    pass
            elif name == "go.mod":
                in_require_block = False
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith('require ('):
                        in_require_block = True
                        continue
                    elif in_require_block and stripped == ')':
                        in_require_block = False
                        continue
                        
                    if in_require_block:
                        parts = stripped.split()
                        if len(parts) >= 2:
                            dependencies.append({
                                "package": parts[0],
                                "version": parts[1],
                                "ecosystem": "Go modules",
                                "type": "Production",
                                "file": rel_path
                            })
                    else:
                        if stripped.startswith('require '):
                            parts = stripped.split()
                            if len(parts) >= 3:
                                dependencies.append({
                                    "package": parts[1],
                                    "version": parts[2],
                                    "ecosystem": "Go modules",
                                    "type": "Production",
                                    "file": rel_path
                                })
            elif name == "pom.xml":
                import xml.etree.ElementTree as ET
                try:
                    root = ET.fromstring(content)
                    for dep in root.iter():
                        if dep.tag.endswith('dependency'):
                            group_id = ""
                            artifact_id = ""
                            version = "latest"
                            for child in dep:
                                if child.tag.endswith('groupId'):
                                    group_id = child.text
                                elif child.tag.endswith('artifactId'):
                                    artifact_id = child.text
                                elif child.tag.endswith('version'):
                                    version = child.text
                            if artifact_id:
                                dep_name = f"{group_id}:{artifact_id}" if group_id else artifact_id
                                dependencies.append({
                                    "package": dep_name,
                                    "version": version or "latest",
                                    "ecosystem": "Maven",
                                    "type": "Production",
                                    "file": rel_path
                                })
                except Exception:
                    pass
            elif name == "composer.json":
                try:
                    data = json.loads(content)
                    for key, dep_type in [("require", "Production"), ("require-dev", "Development")]:
                        deps = data.get(key, {})
                        for dep_name, constraint in deps.items():
                            if dep_name != "php":
                                dependencies.append({
                                    "package": dep_name,
                                    "version": constraint,
                                    "ecosystem": "Composer (PHP)",
                                    "type": dep_type,
                                    "file": rel_path
                                })
                except Exception:
                    pass
            elif name == "Gemfile":
                import re
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith('gem '):
                        match = re.findall(r'[\'"]([^\'"]+)[\'"]', stripped)
                        if match:
                            dep_name = match[0]
                            version = match[1] if len(match) > 1 else "latest"
                            dependencies.append({
                                "package": dep_name,
                                "version": version,
                                "ecosystem": "RubyGems",
                                "type": "Production",
                                "file": rel_path
                            })
                            
        return dependencies

    def _get_developer_annotations(self) -> List[Dict[str, Any]]:
        import re
        annotations = []
        for f in self.scanned:
            filepath = Path(self.results['root_path']) / f['file']
            if not filepath.exists() or not filepath.is_file():
                continue
            try:
                content = filepath.read_text(encoding='utf-8')
            except Exception:
                try:
                    content = filepath.read_text(encoding='latin-1')
                except Exception:
                    continue
                    
            lines = content.splitlines()
            for idx, line in enumerate(lines, 1):
                stripped = line.strip()
                match = re.search(r'(#|//)\s*\b(TODO|FIXME|HACK|BUG|SECURITY)\b(.*)', stripped, re.IGNORECASE)
                if match:
                    tag = match.group(2).upper()
                    msg = match.group(3).strip().strip(':').strip()
                    annotations.append({
                        'file': f['file'],
                        'line': idx,
                        'tag': tag,
                        'message': msg if msg else "(No message details)"
                    })
        return annotations

    def _get_estimated_structure_counts(self) -> Dict[str, int]:
        total_classes = 0
        total_functions = 0
        
        for f in self.scanned:
            filepath = Path(self.results['root_path']) / f['file']
            if not filepath.exists() or not filepath.is_file():
                continue
            try:
                content = filepath.read_text(encoding='utf-8')
            except Exception:
                try:
                    content = filepath.read_text(encoding='latin-1')
                except Exception:
                    continue
            
            lines = content.splitlines()
            ext = filepath.suffix.lower()
            
            for line in lines:
                stripped = line.strip()
                if ext == '.py':
                    if stripped.startswith('class '):
                        total_classes += 1
                    elif stripped.startswith('def ') or stripped.startswith('async def '):
                        total_functions += 1
                elif ext in ('.js', '.ts', '.jsx', '.tsx'):
                    if stripped.startswith('class '):
                        total_classes += 1
                    elif 'function ' in stripped or '=>' in stripped or stripped.startswith('async function '):
                        total_functions += 1
                elif ext in ('.java', '.kt', '.kts', '.cs'):
                    if 'class ' in stripped or 'interface ' in stripped:
                        total_classes += 1
                    elif ('public ' in stripped or 'private ' in stripped or 'protected ' in stripped) and '(' in stripped and ')' in stripped and '=' not in stripped:
                        total_functions += 1
                elif ext in ('.c', '.cpp', '.h', '.hpp'):
                    if 'class ' in stripped or 'struct ' in stripped:
                        total_classes += 1
                    elif '(' in stripped and ')' in stripped and '{' in stripped and '=' not in stripped:
                        total_functions += 1
                        
        return {
            'estimated_classes': total_classes,
            'estimated_functions': total_functions
        }
