import os
import re
import math
import json
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from tabulate import tabulate

from archon.core.parser import LANGUAGE_RULES, get_language_name
from archon.modules.code_metrics import format_size

SEVERITY_ORDER = {
    "Critical": 0,
    "High": 1,
    "Medium": 2,
    "Low": 3,
    "Informational": 4
}

KEYWORDS = {
    'if', 'while', 'for', 'switch', 'catch', 'synchronized', 'lock', 'using',
    'else', 'elif', 'def', 'class', 'interface', 'enum', 'fun', 'function',
    'return', 'throw', 'try', 'finally', 'assert', 'with', 'import', 'from',
    'package', 'public', 'private', 'protected', 'static', 'final'
}

LAYERS = [
    ("cli", ["cli.py"]),
    ("modules", ["modules/"]),
    ("core", ["core/"])
]

def clean_file_content(content: str, language: str) -> Tuple[str, List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Strips comments and string literals, replacing contents with spaces.
    Returns (cleaned_content, comments, strings).
    """
    rules = LANGUAGE_RULES.get(language, {'line_comments': [], 'block_comments': [], 'string_delims': []})
    clean_chars = list(content)
    comments = []
    strings = []
    
    n = len(content)
    i = 0
    line_num = 1
    
    in_block = False
    block_end = None
    block_start_idx = -1
    block_start_line = -1
    
    in_str = False
    str_delim = None
    str_start_idx = -1
    str_start_line = -1
    
    block_comments = sorted(rules.get('block_comments', []), key=lambda x: len(x[0]), reverse=True)
    line_comments = sorted(rules.get('line_comments', []), key=lambda x: len(x), reverse=True)
    string_delims = sorted(rules.get('string_delims', []), key=lambda x: len(x), reverse=True)
    
    while i < n:
        char = content[i]
        
        if char == '\n':
            line_num += 1
            i += 1
            continue
            
        if in_block:
            if content[i:].startswith(block_end):
                end_len = len(block_end)
                for idx in range(block_start_idx, i + end_len):
                    if content[idx] not in ('\n', '\r'):
                        clean_chars[idx] = ' '
                comments.append({
                    'line': block_start_line,
                    'content': content[block_start_idx : i + end_len],
                    'type': 'block'
                })
                i += end_len
                in_block = False
                block_end = None
            else:
                i += 1
            continue
            
        if in_str:
            if char == '\\' and i + 1 < n:
                i += 2
                continue
            if content[i:].startswith(str_delim):
                delim_len = len(str_delim)
                for idx in range(str_start_idx + delim_len, i):
                    if content[idx] not in ('\n', '\r'):
                        clean_chars[idx] = ' '
                strings.append({
                    'line': str_start_line,
                    'content': content[str_start_idx : i + delim_len]
                })
                i += delim_len
                in_str = False
                str_delim = None
            else:
                i += 1
            continue
            
        found_block = False
        for start, end in block_comments:
            if content[i:].startswith(start):
                in_block = True
                block_end = end
                block_start_idx = i
                block_start_line = line_num
                i += len(start)
                found_block = True
                break
        if found_block:
            continue
            
        found_line = False
        for l_comment in line_comments:
            if content[i:].startswith(l_comment):
                start_idx = i
                while i < n and content[i] not in ('\n', '\r'):
                    i += 1
                for idx in range(start_idx, i):
                    clean_chars[idx] = ' '
                comments.append({
                    'line': line_num,
                    'content': content[start_idx:i],
                    'type': 'line'
                })
                found_line = True
                break
        if found_line:
            continue
            
        found_str = False
        for delim in string_delims:
            if content[i:].startswith(delim):
                in_str = True
                str_delim = delim
                str_start_idx = i
                str_start_line = line_num
                i += len(delim)
                found_str = True
                break
        if found_str:
            continue
            
        i += 1
        
    if in_block:
        for idx in range(block_start_idx, n):
            if content[idx] not in ('\n', '\r'):
                clean_chars[idx] = ' '
        comments.append({'line': block_start_line, 'content': content[block_start_idx:], 'type': 'block'})
    elif in_str:
        delim_len = len(str_delim)
        for idx in range(str_start_idx + delim_len, n):
            if content[idx] not in ('\n', '\r'):
                clean_chars[idx] = ' '
        strings.append({'line': str_start_line, 'content': content[str_start_idx:]})
        
    return "".join(clean_chars), comments, strings

def find_matching_brace(content: str, start_index: int) -> int:
    idx = content.find('{', start_index)
    if idx == -1:
        return -1
    stack = 1
    i = idx + 1
    n = len(content)
    while i < n:
        if content[i] == '{':
            stack += 1
        elif content[i] == '}':
            stack -= 1
            if stack == 0:
                return i
        i += 1
    return -1

def get_line_number(content: str, index: int) -> int:
    return content[:index].count('\n') + 1

def get_python_scope(lines: List[str], start_line_idx: int) -> int:
    def_line = lines[start_line_idx]
    def_indent = len(def_line) - len(def_line.lstrip())
    end_line_idx = start_line_idx
    for j in range(start_line_idx + 1, len(lines)):
        line = lines[j]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent <= def_indent:
            break
        end_line_idx = j
    return end_line_idx + 1

def resolve_import_path(import_str: str, current_file: str, all_files: List[str]) -> Optional[str]:
    import_str_clean = import_str.strip().replace("'", "").replace('"', '').replace(";", "")
    if import_str_clean.startswith('<') and import_str_clean.endswith('>'):
        return None
    import_str_clean = import_str_clean.strip('<>"')
    
    if import_str_clean.startswith('.'):
        curr_path = Path(current_file)
        parent_dir = curr_path.parent
        resolved = (parent_dir / import_str_clean).resolve()
        for f in all_files:
            f_path = Path(f)
            if f_path.stem == resolved.name or (f_path.parent == resolved and f_path.stem in ('index', 'main')):
                return f
            try:
                if f == str(resolved.relative_to(Path.cwd())):
                    return f
            except ValueError:
                pass
        return None
        
    python_style = import_str_clean.replace('.', '/')
    for f in all_files:
        f_no_ext = f.rsplit('.', 1)[0]
        if f_no_ext == python_style or f_no_ext.endswith('/' + python_style):
            return f
        if f.endswith(python_style + '.py') or f.endswith(python_style + '/__init__.py'):
            return f
            
    for f in all_files:
        if f.endswith(import_str_clean) or import_str_clean in f:
            return f
            
    return None

class CodeAnalysisReporter:
    def __init__(self, results: Dict[str, Any], output_root: Path):
        self.results = results
        self.output_root = output_root
        self.root_path = Path(results['root_path'])
        self.scanned = results['files_scanned']
        self.ignored = results['files_ignored']
        self.scan_duration = results['scan_duration']
        self.scan_id = results.get('scan_id', 'N/A')
        
        self.findings: List[Dict[str, Any]] = []
        self.file_analyses: Dict[str, Dict[str, Any]] = {}
        self.circular_chains: List[List[str]] = []
        self.duplicate_blocks_list: List[Dict[str, Any]] = []
        self.duplicate_comments_list: List[Dict[str, Any]] = []
        self.duplicate_constants_list: List[Dict[str, Any]] = []
        self.duplicate_strings_list: List[Dict[str, Any]] = []
        self.duplicate_files_list: List[Dict[str, Any]] = []
        self.near_duplicate_files: List[Dict[str, Any]] = []
        self.import_frequencies: Dict[str, int] = {}
        self.shared_modules: List[str] = []
        self.unused_internal_modules: List[str] = []
        
        # Load previous scan history
        self.prev_quality = self._load_previous_quality_summary()
        self.prev_complexities = self._load_previous_file_complexities()
        self.prev_maintainability = self._load_previous_maintainability()
        
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
            prev_folder = dirs[current_index - 1] / "03_Code_Analysis"
            if prev_folder.exists():
                return prev_folder
        except Exception:
            pass
        return None

    def _load_previous_quality_summary(self) -> Dict[str, Any]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        p = prev_folder / "01_quality_summary.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {}

    def _load_previous_file_complexities(self) -> Dict[str, Dict[str, Any]]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        p = prev_folder / "02_complexity_analysis.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding='utf-8'))
                res = {}
                fc = data.get('file_complexities', [])
                for item in fc:
                    if isinstance(item, list) and len(item) > 0:
                        res[item[0]] = {
                            'cyclomatic': item[1],
                            'cognitive': item[2],
                            'nesting_depth': item[3]
                        }
                    elif isinstance(item, dict) and 'file' in item:
                        res[item['file']] = item
                return res
            except Exception:
                pass
        return {}

    def _load_previous_maintainability(self) -> Dict[str, Dict[str, Any]]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        p = prev_folder / "09_maintainability.json"
        if p.exists():
            try:
                data = json.loads(p.read_text(encoding='utf-8'))
                res = {}
                for item in data.get('maintainability', []):
                    if 'file' in item:
                        res[item['file']] = item
                return res
            except Exception:
                pass
        return {}

    def _get_diff_text(self, curr: float, prev: Optional[float], is_pct: bool = False) -> str:
        if prev is None:
            return " [NEW]"
        diff = curr - prev
        if diff == 0:
            return " (0)"
        sign = "+" if diff > 0 else ""
        if is_pct:
            return f" ({sign}{diff:.2f}%)"
        if isinstance(diff, float):
            return f" ({sign}{diff:.2f})"
        return f" ({sign}{diff:+d})"
        
    def generate_reports(self):
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._run_analysis()
        
        # Output reports
        self._report_02_complexity_analysis()
        self._report_03_function_analysis()
        self._report_04_class_analysis()
        self._report_05_dependency_analysis()
        self._report_06_duplication_analysis()
        self._report_07_architecture_analysis()
        self._report_08_code_smells()
        self._report_09_maintainability()
        self._report_10_scan_metadata()
        self._report_01_quality_summary() # summary goes last
        
        # Generate interactive HTML report
        from archon.core.html_generator import compile_and_write_html_report
        nav = {"prev": "../02_security/report.html", "next": "../04_Contributor_Analysis/report.html"}
        compile_and_write_html_report(self.output_root, self.results, "Code Analysis (Module 03)", nav)
        
    def _get_footer(self) -> str:
        local_time = time.localtime(self.results.get('start_time', time.time()))
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
        return (
            "\n\n=========================================\n"
            "Generated by Archon One Code Analysis\n"
            "Version: 0.2.0\n"
            f"Scan ID: {self.scan_id}\n"
            f"Repository Name: {self.root_path.name}\n"
            f"Timestamp: {timestamp_str}\n"
            f"Total Scan Duration: {self.scan_duration:.4f} seconds\n"
            "=========================================\n"
        )
        
    def _write_files(self, base_name: str, txt_content: str, json_data: Any):
        self.output_root.mkdir(parents=True, exist_ok=True)
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
        
    def _add_finding(self, file: str, line: Optional[int], severity: str, category: str, rule: str, reason: str, impact: str, fix: str, difficulty: str = "Medium"):
        priority = "Low"
        if severity in ("Critical", "High"):
            priority = "High"
        elif severity == "Medium":
            priority = "Medium"
            
        finding = {
            "file": file,
            "line": line,
            "severity": severity,
            "category": category,
            "rule": rule,
            "reason": reason,
            "impact": impact,
            "suggested_fix": fix,
            "priority": priority,
            "estimated_difficulty": difficulty
        }
        self.findings.append(finding)
        
    def _run_analysis(self):
        all_scanned_files = [f['file'] for f in self.scanned]
        dependency_graph = {}
        
        # 1. Base File Parsing
        for f in self.scanned:
            rel_path = f['file']
            filepath = self.root_path / rel_path
            lang_id = f['lang_id']
            
            try:
                content = filepath.read_text(encoding='utf-8')
            except Exception:
                try:
                    content = filepath.read_text(encoding='latin-1')
                except Exception:
                    continue
                    
            clean_content, comments, strings = clean_file_content(content, lang_id)
            clean_lines = clean_content.splitlines()
            
            complexity = self._analyze_complexity(clean_content, clean_lines, lang_id)
            functions, classes = self._analyze_functions_and_classes(clean_content, clean_lines, rel_path, lang_id, comments)
            imports = self._analyze_imports(clean_content, clean_lines, rel_path, lang_id, all_scanned_files)
            dependency_graph[rel_path] = imports['resolved_internal']
            
            # Map import frequencies
            for imp in imports['all']:
                self.import_frequencies[imp] = self.import_frequencies.get(imp, 0) + 1
                
            self.file_analyses[rel_path] = {
                'file': rel_path,
                'language': f['language'],
                'lang_id': lang_id,
                'loc': f['physical_loc'],
                'logical_loc': f['logical_loc'],
                'blank_lines': f['blank_lines'],
                'comment_lines': f['comment_lines'],
                'comment_density': f['comment_density'],
                'clean_content': clean_content,
                'clean_lines': clean_lines,
                'comments': comments,
                'strings': strings,
                'complexity': complexity,
                'functions': functions,
                'classes': classes,
                'imports': imports,
                'smells': [],
                'naming_smells': []
            }
            
        # 2. Build Dependency Tree Depth & Circular References
        self.circular_chains = self._find_dependency_cycles(dependency_graph)
        
        # Shared Modules detection
        for imp, freq in self.import_frequencies.items():
            if freq >= 3:
                self.shared_modules.append(imp)
                
        # Unused internal modules (Dead Modules)
        imported_internal_set = set()
        for fa in self.file_analyses.values():
            imported_internal_set.update(fa['imports']['resolved_internal'])
        for f in all_scanned_files:
            # Exclude known entry points like main.py, cli.py
            if f not in imported_internal_set and not any(x in f.lower() for x in ('main.py', 'cli.py', 'index.js')):
                self.unused_internal_modules.append(f)
                
        # 3. Class Inheritance graph & Child Class Count / Largest Chain
        self._analyze_class_inheritance()
        
        # 4. Duplication Analysis
        self._analyze_duplication()
        
        # 5. Smell & Naming Checks & Maintainability calculations
        for rel_path, analysis in self.file_analyses.items():
            self._analyze_code_smells_for_file(analysis)
            self._analyze_naming_for_file(analysis)
            self._calculate_maintainability_for_file(analysis)
            
    def _analyze_complexity(self, clean_content: str, clean_lines: List[str], lang_id: str) -> Dict[str, Any]:
        cc = 1
        cog = 0
        max_nesting = 0
        decisions = 0
        loops = 0
        branches = 0
        switches = 0
        boolean_exprs = 0
        
        if lang_id in ('python', 'yaml'):
            cc_pattern = re.compile(r'\b(if|elif|while|for|except|and|or)\b')
            decision_pattern = re.compile(r'\b(if|elif)\b')
            loop_pattern = re.compile(r'\b(while|for)\b')
            branch_pattern = re.compile(r'\b(if|elif|else)\b')
            bool_pattern = re.compile(r'\b(and|or)\b')
        else:
            cc_pattern = re.compile(r'\b(if|while|for|catch|case)\b|&&|\|\||\?')
            decision_pattern = re.compile(r'\b(if|case)\b|\?')
            loop_pattern = re.compile(r'\b(while|for|do)\b')
            branch_pattern = re.compile(r'\b(if|else)\b')
            bool_pattern = re.compile(r'&&|\|\||\b(and|or)\b')
            switches = clean_content.count('switch') + clean_content.count('match')
            
        cc += len(cc_pattern.findall(clean_content))
        decisions = len(decision_pattern.findall(clean_content))
        loops = len(loop_pattern.findall(clean_content))
        branches = len(branch_pattern.findall(clean_content))
        boolean_exprs = len(bool_pattern.findall(clean_content))
        
        # Nesting
        curr_nesting = 0
        if lang_id in ('python', 'yaml'):
            for line in clean_lines:
                if not line.strip():
                    continue
                indent = len(line) - len(line.lstrip())
                depth = indent // 4
                if depth > max_nesting:
                    max_nesting = depth
                if any(x in line for x in ('if ', 'elif ', 'while ', 'for ', 'except ')):
                    cog += 1 + depth
        else:
            for char in clean_content:
                if char == '{':
                    curr_nesting += 1
                    if curr_nesting > max_nesting:
                        max_nesting = curr_nesting
                elif char == '}':
                    curr_nesting = max(0, curr_nesting - 1)
            for line in clean_lines:
                if any(x in line for x in ('if', 'while', 'for', 'catch', 'case')):
                    depth = line.count('{')
                    cog += 1 + depth
                    
        return {
            'cyclomatic': cc,
            'cognitive': cog,
            'nesting_depth': max_nesting,
            'decision_count': decisions,
            'loop_count': loops,
            'branch_count': branches,
            'switch_count': switches,
            'boolean_expr_count': boolean_exprs
        }
        
    def _analyze_functions_and_classes(self, clean_content: str, clean_lines: List[str], rel_path: str, lang_id: str, comments: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        functions = []
        classes = []
        
        class_regexes = {
            'python': re.compile(r'class\s+([A-Za-z0-9_]+)(?:\s*\(([^)]*)\))?\s*:'),
            'java': re.compile(r'\b(?:class|interface|enum)\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_<>]+))?(?:\s+implements\s+([A-Za-z0-9_,\s<>]+))?\b'),
            'kotlin': re.compile(r'\b(?:class|interface|enum\s+class|object)\s+([A-Za-z0-9_]+)(?:\s*:\s*([A-Za-z0-9_,\s<>()]+))?\b'),
            'javascript': re.compile(r'\bclass\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_]+))?\b'),
            'typescript': re.compile(r'\b(?:class|interface)\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_]+))?\b'),
            'php': re.compile(r'\b(?:class|interface|trait)\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_]+))?\b'),
            'dart': re.compile(r'\bclass\s+([A-Za-z0-9_]+)(?:\s+extends\s+([A-Za-z0-9_]+))?\b'),
            'cpp': re.compile(r'\b(?:class|struct)\s+([A-Za-z0-9_]+)(?:\s*:\s*(?:public|protected|private)?\s*([A-Za-z0-9_<>]+))?\b')
        }
        
        class_re = class_regexes.get(lang_id)
        if class_re:
            for match in class_re.finditer(clean_content):
                name = match.group(1)
                parent = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else "None"
                idx = match.start()
                start_line = get_line_number(clean_content, idx)
                
                if lang_id in ('python', 'yaml'):
                    end_line = get_python_scope(clean_lines, start_line - 1)
                else:
                    end_idx = find_matching_brace(clean_content, idx)
                    end_line = get_line_number(clean_content, end_idx) if end_idx != -1 else len(clean_lines)
                    
                classes.append({
                    'name': name,
                    'file': rel_path,
                    'start_line': start_line,
                    'end_line': end_line,
                    'loc': end_line - start_line + 1,
                    'parent': parent,
                    'methods': [],
                    'attributes': [],
                    'constructors': 0,
                    'static_methods': 0,
                    'public_methods': 0,
                    'private_methods': 0,
                    'protected_methods': 0,
                    'is_interface': 'interface' in match.group(0),
                    'is_enum': 'enum' in match.group(0),
                    'is_abstract': 'abstract' in match.group(0),
                    'inheritance_depth': 0,
                    'child_count': 0
                })
                
        func_regexes = {
            'python': re.compile(r'\bdef\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)'),
            'brace_based': re.compile(r'\b([A-Za-z0-9_]+)\s*\(([^)]*)\)(?:\s*[^{]*)\s*\{'),
            'arrow': re.compile(r'\b(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:\async\s*)?\(([^)]*)\)\s*=>')
        }
        
        matched_funcs = []
        if lang_id == 'python':
            for match in func_regexes['python'].finditer(clean_content):
                matched_funcs.append((match.group(1), match.group(2), match.start(), 'python'))
        elif lang_id in ('javascript', 'typescript', 'java', 'kotlin', 'dart', 'cpp', 'c', 'php'):
            for match in func_regexes['brace_based'].finditer(clean_content):
                name = match.group(1)
                if name not in KEYWORDS:
                    matched_funcs.append((name, match.group(2), match.start(), 'brace'))
            if lang_id in ('javascript', 'typescript'):
                for match in func_regexes['arrow'].finditer(clean_content):
                    matched_funcs.append((match.group(1), match.group(2), match.start(), 'arrow'))
                    
        for name, params_str, idx, func_type in matched_funcs:
            start_line = get_line_number(clean_content, idx)
            if func_type == 'python':
                end_line = get_python_scope(clean_lines, start_line - 1)
            else:
                end_idx = find_matching_brace(clean_content, idx)
                end_line = get_line_number(clean_content, end_idx) if end_idx != -1 else len(clean_lines)
                
            body_content = "\n".join(clean_lines[start_line - 1 : end_line])
            
            has_print = 'print(' in body_content or 'console.log' in body_content or 'cout' in body_content
            has_assignment = '=' in body_content
            is_pure = not (has_print or has_assignment)
            
            params = [p.strip() for p in params_str.split(',') if p.strip()]
            returns = len(re.findall(r'\breturn\b', body_content))
            
            local_vars = len(re.findall(r'\b(let|const|var|val)\s+([A-Za-z0-9_]+)', body_content))
            if local_vars == 0:
                local_vars = len(re.findall(r'\b([a-zA-Z0-9_]+)\s*=[^=]', body_content))
                
            doc_present = False
            for comment in comments:
                if start_line <= comment['line'] <= start_line + 3:
                    doc_present = True
                    break
                    
            # Loop and branch counting per function
            fn_loops = len(re.findall(r'\b(for|while)\b', body_content))
            fn_branches = len(re.findall(r'\b(if|elif|else)\b', body_content))
            
            # Callback keywords check
            callbacks = sum(1 for p in params if any(x in p.lower() for x in ('cb', 'callback', 'handler')))
            
            functions.append({
                'name': name,
                'file': rel_path,
                'start_line': start_line,
                'end_line': end_line,
                'loc': end_line - start_line + 1,
                'parameters': len(params),
                'returns': returns,
                'local_vars': local_vars,
                'is_pure': is_pure,
                'recursive': f"{name}(" in body_content,
                'async': 'async' in clean_lines[start_line - 1] or 'suspend' in clean_lines[start_line - 1],
                'generator': 'yield' in body_content,
                'lambda': func_type == 'arrow',
                'empty': len(body_content.replace('{', '').replace('}', '').strip()) <= 5,
                'doc_present': doc_present,
                'calls': len(re.findall(r'\b([A-Za-z0-9_]+)\s*\((?![^{]*\})', body_content)),
                'loops': fn_loops,
                'branches': fn_branches,
                'callbacks': callbacks
            })
            
        for c in classes:
            c_methods = []
            for f in functions:
                if c['start_line'] <= f['start_line'] <= c['end_line']:
                    c_methods.append(f)
            c['methods'] = c_methods
            
            for m in c_methods:
                m_header = clean_lines[m['start_line'] - 1]
                if 'static' in m_header or '@staticmethod' in clean_lines[max(0, m['start_line'] - 2)]:
                    c['static_methods'] += 1
                if 'private' in m_header or m['name'].startswith('__'):
                    c['private_methods'] += 1
                elif 'protected' in m_header or m['name'].startswith('_'):
                    c['protected_methods'] += 1
                else:
                    c['public_methods'] += 1
                if m['name'] in ('__init__', '__construct', 'constructor') or m['name'] == c['name']:
                    c['constructors'] += 1
                    
            for j in range(c['start_line'] - 1, c['end_line']):
                line = clean_lines[j]
                in_method = False
                for m in c_methods:
                    if m['start_line'] <= j + 1 <= m['end_line']:
                        in_method = True
                        break
                if not in_method and '=' in line and not line.strip().startswith(('class', 'def', 'fun')):
                    c['attributes'].append(line.split('=')[0].strip())
                    
        return functions, classes
        
    def _analyze_imports(self, clean_content: str, clean_lines: List[str], rel_path: str, lang_id: str, all_files: List[str]) -> Dict[str, Any]:
        internal = []
        external = []
        resolved_internal = []
        duplicates = []
        wildcards = []
        unused = []
        broken = []
        self_imports = []
        
        import_patterns = {
            'python': [
                re.compile(r'^\s*import\s+([A-Za-z0-9_.,\s]+)'),
                re.compile(r'^\s*from\s+([A-Za-z0-9_.]+)\s+import\s+([A-Za-z0-9_*.,\s]+)')
            ],
            'java': [re.compile(r'^\s*import\s+(?:static\s+)?([A-Za-z0-9_.*]+);')],
            'kotlin': [re.compile(r'^\s*import\s+([A-Za-z0-9_.*]+)')],
            'cpp': [re.compile(r'^\s*#include\s+([<"][A-Za-z0-9_./\\]+[>"])')],
            'c': [re.compile(r'^\s*#include\s+([<"][A-Za-z0-9_./\\]+[>"])')],
            'javascript': [
                re.compile(r'\bimport\s+.*from\s+[\'"]([^\'"]+)[\'"]'),
                re.compile(r'\brequire\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)')
            ],
            'typescript': [
                re.compile(r'\bimport\s+.*from\s+[\'"]([^\'"]+)[\'"]'),
                re.compile(r'\brequire\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)')
            ],
            'php': [
                re.compile(r'\buse\s+([A-Za-z0-9_\\]+);'),
                re.compile(r'\b(?:require|include)(?:_once)?\s*\(?\s*[\'"]([^\'"]+)[\'"]\s*\)?')
            ],
            'dart': [re.compile(r'\bimport\s+[\'"]([^\'"]+)[\'"]')]
        }
        
        patterns = import_patterns.get(lang_id, [])
        seen_imports = set()
        
        for line in clean_lines:
            for pat in patterns:
                for match in pat.finditer(line):
                    import_val = match.group(1).strip()
                    if '*' in import_val:
                        wildcards.append(import_val)
                    if import_val in seen_imports:
                        duplicates.append(import_val)
                    else:
                        seen_imports.add(import_val)
                        
                    resolved = resolve_import_path(import_val, rel_path, all_files)
                    if resolved:
                        if resolved == rel_path:
                            self_imports.append(import_val)
                        else:
                            internal.append(import_val)
                            resolved_internal.append(resolved)
                    else:
                        if any(x in import_val for x in ('.', '/', '\\')) and not import_val.startswith(('java.', 'kotlin.', 'std', 'vector', 'iostream')):
                            broken.append(import_val)
                        else:
                            external.append(import_val)
                            
        for imp in seen_imports:
            short_name = imp.split('.')[-1].split('/')[-1].replace(';', '').strip()
            occurrences = len(re.findall(r'\b' + re.escape(short_name) + r'\b', clean_content))
            if occurrences <= 1:
                unused.append(imp)
                
        return {
            'all': list(seen_imports),
            'internal': internal,
            'external': external,
            'resolved_internal': resolved_internal,
            'duplicates': duplicates,
            'wildcards': wildcards,
            'unused': unused,
            'broken': broken,
            'self_imports': self_imports
        }
        
    def _find_dependency_cycles(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        visited = {}
        path = []
        cycles = []
        
        def dfs(node):
            if node in visited:
                if visited[node] == 1:
                    idx = path.index(node)
                    cycles.append(path[idx:] + [node])
                return
            visited[node] = 1
            path.append(node)
            for neighbor in graph.get(node, []):
                dfs(neighbor)
            path.pop()
            visited[node] = 2
            
        for node in graph:
            if node not in visited:
                dfs(node)
        return cycles
        
    def _analyze_class_inheritance(self):
        # Build parent-child relationships
        classes_map = {}
        all_classes_list = []
        for analysis in self.file_analyses.values():
            for cl in analysis['classes']:
                classes_map[cl['name']] = cl
                all_classes_list.append(cl)
                
        # Calculate inheritance depths
        for cl in all_classes_list:
            depth = 0
            curr = cl
            visited = set()
            while curr and curr['parent'] != "None" and curr['parent'] not in visited:
                visited.add(curr['name'])
                parent_name = curr['parent'].split('(')[0].split('<')[0].strip()
                if parent_name in classes_map:
                    depth += 1
                    curr = classes_map[parent_name]
                    curr['child_count'] += 1
                else:
                    depth += 1
                    break
            cl['inheritance_depth'] = depth
            
    def _analyze_duplication(self):
        line_hashes = {}
        file_contents = {}
        
        for rel_path, analysis in self.file_analyses.items():
            lines = [line.strip() for line in analysis['clean_lines'] if line.strip()]
            analysis['stripped_lines'] = lines
            
            # File contents hashing for duplicate files
            clean_text = analysis['clean_content'].strip()
            content_hash = hashlib.md5(clean_text.encode('utf-8')).hexdigest() if clean_text else "empty"
            if content_hash not in file_contents:
                file_contents[content_hash] = []
            file_contents[content_hash].append(rel_path)
            
            # Extract constants
            constants = re.findall(r'\b([A-Z_0-9]+)\s*=\s*(.*)', analysis['clean_content'])
            for name, val in constants:
                self.duplicate_constants_list.append({'file': rel_path, 'name': name, 'value': val.strip()})
                
            # Sliding window for duplicate blocks
            window_size = 6
            for j in range(len(lines) - window_size + 1):
                window = "\n".join(lines[j : j + window_size])
                win_hash = hash(window)
                if win_hash not in line_hashes:
                    line_hashes[win_hash] = []
                line_hashes[win_hash].append((rel_path, j + 1, window))
                
        # Group duplicates
        dup_blocks = []
        for win_hash, locations in line_hashes.items():
            if len(locations) > 1:
                for a_idx in range(len(locations)):
                    for b_idx in range(a_idx + 1, len(locations)):
                        file_a, line_a, text_a = locations[a_idx]
                        file_b, line_b, _ = locations[b_idx]
                        if file_a != file_b:
                            dup_blocks.append({
                                'file_a': file_a,
                                'line_a': line_a,
                                'file_b': file_b,
                                'line_b': line_b,
                                'length': 6,
                                'text': text_a[:40] + "..."
                            })
        self.duplicate_blocks_list = sorted(dup_blocks, key=lambda x: (x['file_a'], x['line_a']))[:100]
        
        # Duplicate files
        for h, paths in file_contents.items():
            if len(paths) > 1:
                for i in range(len(paths)):
                    for j in range(i + 1, len(paths)):
                        self.duplicate_files_list.append({'file_a': paths[i], 'file_b': paths[j]})
                        
        # Duplicate comments, strings
        comment_groups = {}
        string_groups = {}
        for rel_path, analysis in self.file_analyses.items():
            for comment in analysis['comments']:
                c_text = comment['content'].strip()
                if len(c_text) > 10:
                    if c_text not in comment_groups:
                        comment_groups[c_text] = []
                    comment_groups[c_text].append((rel_path, comment['line']))
            for s in analysis['strings']:
                s_text = s['content'].strip()
                if len(s_text) > 10:
                    if s_text not in string_groups:
                        string_groups[s_text] = []
                    string_groups[s_text].append((rel_path, s['line']))
                    
        for text, locs in comment_groups.items():
            if len(locs) > 1:
                self.duplicate_comments_list.append({'text': text[:50], 'occurrences': len(locs), 'locations': locs})
        for text, locs in string_groups.items():
            if len(locs) > 1:
                self.duplicate_strings_list.append({'text': text[:50], 'occurrences': len(locs), 'locations': locs})
                
        # Near duplicate files (similarity > 70%)
        all_paths = list(self.file_analyses.keys())
        for idx_a in range(len(all_paths)):
            for idx_b in range(idx_a + 1, len(all_paths)):
                f_a = all_paths[idx_a]
                f_b = all_paths[idx_b]
                lines_a = set(self.file_analyses[f_a]['stripped_lines'])
                lines_b = set(self.file_analyses[f_b]['stripped_lines'])
                if lines_a or lines_b:
                    sim = len(lines_a & lines_b) / max(1, len(lines_a | lines_b))
                    if sim > 0.70 and sim < 1.0:
                        self.near_duplicate_files.append({'file_a': f_a, 'file_b': f_b, 'similarity': sim})
                        
    def _analyze_code_smells_for_file(self, analysis: Dict[str, Any]):
        rel_path = analysis['file']
        clean_lines = analysis['clean_lines']
        clean_content = analysis['clean_content']
        comments = analysis['comments']
        
        # Load configurable thresholds
        thresholds = self.config.get('thresholds', {})
        max_file_len = thresholds.get('max_file_length', 1000)
        max_func_len = thresholds.get('max_function_length', 100)
        max_params = thresholds.get('max_parameters', 5)
        max_class_len = thresholds.get('max_class_length', 500)
        max_imports = thresholds.get('max_import_count', 20)
        min_comment_density = thresholds.get('min_comment_density', 10.0)
        
        # Long/Oversized Module Smell
        if analysis['loc'] > max_file_len:
            analysis['smells'].append('Oversized Module')
            self._add_finding(rel_path, 1, "High", "Code Smell", "Oversized Module", 
                              f"File contains {analysis['loc']} lines of code, exceeding the limit of {max_file_len}.",
                              "Oversized modules represent monolithic files that are hard to navigate and maintain.",
                              "Decompose the file into smaller, specialized helper modules.")
                              
        # Excessive Imports
        if len(analysis['imports']['all']) > max_imports:
            analysis['smells'].append('Excessive Imports')
            self._add_finding(rel_path, None, "Low", "Code Smell", "Excessive Imports",
                              f"File has {len(analysis['imports']['all'])} imports, exceeding the limit of {max_imports}.",
                              "Excessive imports increase coupling and make modular testing difficult.",
                              "Consolidate modules or reduce direct linkages.")
                              
        # Low Comment Density
        if analysis['comment_density'] < min_comment_density:
            analysis['smells'].append('Low Comment Density')
            self._add_finding(rel_path, None, "Low", "Code Smell", "Low Comment Density",
                              f"File has {analysis['comment_density']:.2f}% comment density, which is below the minimum of {min_comment_density}%.",
                              "Low documentation density makes understanding and maintaining code harder for developers.",
                              "Add descriptive docstrings and inline explanation comments.")
                              
        for f in analysis['functions']:
            if f['loc'] > max_func_len:
                analysis['smells'].append('God Function')
                self._add_finding(rel_path, f['start_line'], "Medium", "Code Smell", "God Function",
                                  f"Function '{f['name']}' has {f['loc']} LOC, exceeding {max_func_len} lines.",
                                  "Long functions increase cognitive complexity and nesting.",
                                  "Extract sub-logic into separate single-responsibility helper functions.")
            if f['parameters'] > max_params:
                analysis['smells'].append('Excessive Parameters')
                self._add_finding(rel_path, f['start_line'], "Low", "Code Smell", "Excessive Parameters",
                                  f"Function '{f['name']}' has {f['parameters']} parameters, exceeding the limit of {max_params}.",
                                  "Large parameters list increases function coupling and makes testing difficult.",
                                  "Create a configuration object or group parameters into a container class.")
                                  
        for c in analysis['classes']:
            if c['loc'] > max_class_len:
                analysis['smells'].append('Blob Class')
                self._add_finding(rel_path, c['start_line'], "High", "Code Smell", "Blob Class",
                                  f"Class '{c['name']}' has {c['loc']} LOC, exceeding {max_class_len} lines.",
                                  "God or Blob classes violation the single responsibility principle.",
                                  "Decompose the class behavior into smaller, delegate components.")
            elif c['loc'] < 15 and len(c['methods']) <= 1:
                analysis['smells'].append('Lazy Class')
                self._add_finding(rel_path, c['start_line'], "Low", "Code Smell", "Lazy Class",
                                  f"Class '{c['name']}' is extremely small ({c['loc']} lines) with negligible behavior.",
                                  "Lazy classes increase project structural complexity without added benefit.",
                                  "Inline the class or merge it with another relevant module.")
                                  
        # Switch cases duplicates / Repeated switch structures
        switch_matches = re.findall(r'case\s+([^:]+):', clean_content)
        if len(switch_matches) != len(set(switch_matches)):
            analysis['smells'].append('Repeated Switch Cases')
            self._add_finding(rel_path, None, "Medium", "Code Smell", "Repeated Switch Cases",
                              "Duplicate case expressions found inside switch/match structures.",
                              "Repeated case blocks lead to unreachable branches and bugs.",
                              "Consolidate matching logic or extract into a polymorphism strategy.")
                              
        # Message chains: check for excessive chaining e.g. a.b().c().d()
        for idx, line in enumerate(clean_lines):
            if line.count('.') >= 4:
                analysis['smells'].append('Message Chain')
                self._add_finding(rel_path, idx + 1, "Low", "Code Smell", "Message Chain",
                                  "Line contains excessive chaining of method calls.",
                                  "Message chains violate the Law of Demeter and increase coupling.",
                                  "Introduce intermediate variables or delegate methods.")
                break
                                  
        # Redundant returns / else
        for idx, line in enumerate(clean_lines):
            if 'return' in line and 'return;' in line.replace(' ', ''):
                # void return at the very end of code block
                if idx + 1 < len(clean_lines) and '}' in clean_lines[idx + 1]:
                    analysis['smells'].append('Redundant Return')
                    self._add_finding(rel_path, idx + 1, "Low", "Code Smell", "Redundant Return",
                                      "Redundant return statement at the end of function block.",
                                      "Increases LOC without adding functional logic.",
                                      "Remove the redundant return statement.")
                    break
                                      
        # Empty except/catch blocks
        except_matches = re.finditer(r'except\s*:\s*pass|catch\s*\([^)]*\)\s*\{\s*\}', clean_content)
        for match in except_matches:
            line_num = get_line_number(clean_content, match.start())
            analysis['smells'].append('Empty catch/except')
            self._add_finding(rel_path, line_num, "High", "Code Smell", "Empty catch/except",
                              "Exception is caught but ignored without handling or logging.",
                              "Silences bugs and complicates production issue debugging.",
                              "Add logging or error handler logic inside the catch block.")

        # Empty Class
        for c in analysis['classes']:
            if len(c['methods']) == 0 and len(c['attributes']) == 0:
                analysis['smells'].append('Empty Class')
                self._add_finding(rel_path, c['start_line'], "Low", "Code Smell", "Empty Class",
                                  f"Class '{c['name']}' is empty (has no methods or attributes).",
                                  "Empty classes represent dead code, stub interfaces, or missing implementations.",
                                  "Add fields/behavior or remove the class if it is unused.")

        # Deep Nesting
        max_nesting_threshold = thresholds.get('max_nesting_depth', 5)
        if analysis['complexity']['nesting_depth'] > max_nesting_threshold:
            analysis['smells'].append('Deep Nesting')
            self._add_finding(rel_path, None, "Medium", "Code Smell", "Deep Nesting",
                              f"File has a maximum block nesting depth of {analysis['complexity']['nesting_depth']}, exceeding the limit of {max_nesting_threshold}.",
                              "Deeply nested statements increase cognitive load and complicate unit testing.",
                              "Refactor deeply nested blocks (like nested loops or conditional branches) into helper functions.")
                              
    def _analyze_naming_for_file(self, analysis: Dict[str, Any]):
        rel_path = analysis['file']
        clean_lines = analysis['clean_lines']
        
        # Invalid file name checking
        p = Path(rel_path)
        if ' ' in p.name or '-' in p.name and p.suffix == '.py':
            analysis['naming_smells'].append('Invalid File Name')
            self._add_finding(rel_path, None, "Low", "Naming Analysis", "Invalid File Name",
                              f"File name '{p.name}' contains invalid characters or style violation.",
                              "File names should follow consistent conventions (e.g., snake_case in Python).",
                              "Rename the file using kebab-case or snake_case consistently.")
                              
        # Validate function names, class names, variable names
        for f in analysis['functions']:
            if len(f['name']) > 30:
                analysis['naming_smells'].append('Extremely Long Identifier')
                self._add_finding(rel_path, f['start_line'], "Low", "Naming Analysis", "Extremely Long Identifier",
                                  f"Function name '{f['name']}' is extremely long ({len(f['name'])} characters).",
                                  "Long identifiers clutter code readability.",
                                  "Shorten the identifier to be clear yet concise.")
                                  
            # Single character variables
            local_vars = re.findall(r'\b(let|const|var|val)\s+([a-zA-Z0-9_]+)\b', "\n".join(clean_lines[f['start_line']-1:f['end_line']]))
            for _, name in local_vars:
                if len(name) == 1 and name not in ('i', 'j', 'k', 'x', 'y', 'z'):
                    analysis['naming_smells'].append('Single Character Variable')
                    self._add_finding(rel_path, f['start_line'], "Low", "Naming Analysis", "Single Character Variable",
                                      f"Single character variable name '{name}' detected.",
                                      "Variable names should be descriptive to explain intent.",
                                      "Rename the variable to a meaningful identifier.")
                                      
    def _calculate_maintainability_for_file(self, analysis: Dict[str, Any]):
        loc = analysis['loc']
        cc = analysis['complexity']['cyclomatic']
        cd = analysis['comment_density']
        
        if loc <= 0:
            analysis['maintainability_index'] = 100.0
            analysis['grade'] = 'A'
            analysis['technical_debt_score'] = 0.0
            return
            
        volume = loc * 8.0
        try:
            raw_mi = 171.0 - 5.2 * math.log(volume) - 0.23 * cc - 16.2 * math.log(loc) + 50.0 * math.sin(math.sqrt(2.4 * cd))
            normalized = (raw_mi / 171.0) * 100.0
            mi = max(0.0, min(100.0, normalized))
        except Exception:
            mi = 50.0
            
        analysis['maintainability_index'] = mi
        
        if mi >= 80.0:
            analysis['grade'] = 'A'
        elif mi >= 70.0:
            analysis['grade'] = 'B'
        elif mi >= 60.0:
            analysis['grade'] = 'C'
        elif mi >= 50.0:
            analysis['grade'] = 'D'
        else:
            analysis['grade'] = 'F'
            
        smells_count = len(analysis['smells']) + len(analysis['naming_smells'])
        analysis['technical_debt_score'] = min(100.0, smells_count * 10.0)
        
    def _report_01_quality_summary(self):
        total_files = len(self.file_analyses)
        if total_files == 0:
            return
            
        avg_cc = sum(f['complexity']['cyclomatic'] for f in self.file_analyses.values()) / total_files
        avg_mi = sum(f['maintainability_index'] for f in self.file_analyses.values()) / total_files
        
        all_funcs = []
        for f in self.file_analyses.values():
            all_funcs.extend(f['functions'])
        avg_func_len = sum(fn['loc'] for fn in all_funcs) / max(1, len(all_funcs))
        
        all_classes = []
        for f in self.file_analyses.values():
            all_classes.extend(f['classes'])
        avg_class_len = sum(cl['loc'] for cl in all_classes) / max(1, len(all_classes))
        avg_file_len = sum(f['loc'] for f in self.file_analyses.values()) / total_files
        
        most_complex_file = max(self.file_analyses.values(), key=lambda x: x['complexity']['cyclomatic'], default={'file': 'None', 'complexity': {'cyclomatic': 0}})
        largest_file = max(self.file_analyses.values(), key=lambda x: x['loc'], default={'file': 'None', 'loc': 0})
        largest_class = max(all_classes, key=lambda x: x['loc'], default={'name': 'None', 'loc': 0})
        largest_function = max(all_funcs, key=lambda x: x['loc'], default={'name': 'None', 'loc': 0})
        
        dir_complexities = {}
        for f in self.file_analyses.values():
            p = Path(f['file'])
            parent = str(p.parent)
            if parent not in dir_complexities:
                dir_complexities[parent] = []
            dir_complexities[parent].append(f['complexity']['cyclomatic'])
        highest_risk_dir = max(dir_complexities.items(), key=lambda x: sum(x[1])/len(x[1]), default=('None', [0]))[0]
        
        # Rankings
        top_complex = sorted(self.file_analyses.values(), key=lambda x: x['complexity']['cyclomatic'], reverse=True)[:5]
        top_largest = sorted(self.file_analyses.values(), key=lambda x: x['loc'], reverse=True)[:5]
        lowest_mi = sorted(self.file_analyses.values(), key=lambda x: x['maintainability_index'])[:5]
        highest_debt = sorted(self.file_analyses.values(), key=lambda x: x['technical_debt_score'], reverse=True)[:5]
        
        # Naming scores
        naming_issues_count = sum(len(f['naming_smells']) for f in self.file_analyses.values())
        
        prev_mi = self.prev_quality.get('overall_quality_score')
        prev_grade = self.prev_quality.get('maintainability_grade')
        prev_debt = self.prev_quality.get('technical_debt_score')
        prev_findings = self.prev_quality.get('findings_summary', {}).get('total') if isinstance(self.prev_quality.get('findings_summary'), dict) else self.prev_quality.get('findings_summary')
        if not isinstance(prev_findings, (int, float)):
            prev_findings = None
            
        mi_diff = self._get_diff_text(avg_mi, prev_mi)
        grade_diff = f" (was {prev_grade})" if prev_grade and prev_grade != self._get_repo_grade(avg_mi) else ""
        debt_diff = self._get_diff_text(self._get_repo_debt(), prev_debt)
        findings_diff = self._get_diff_text(len(self.findings), prev_findings)
        
        prev_avg = self.prev_quality.get('averages', {})
        prev_cc = prev_avg.get('complexity')
        prev_func_len = prev_avg.get('function_length')
        prev_class_size = prev_avg.get('class_size')
        prev_file_size = prev_avg.get('file_size')
        
        cc_diff = self._get_diff_text(avg_cc, prev_cc)
        func_len_diff = self._get_diff_text(avg_func_len, prev_func_len)
        class_size_diff = self._get_diff_text(avg_class_len, prev_class_size)
        file_size_diff = self._get_diff_text(avg_file_len, prev_file_size)
        
        txt = "====================================================\n"
        txt += "           01_QUALITY_SUMMARY REPORT                \n"
        txt += "====================================================\n\n"
        txt += f"Overall Quality Score:     {avg_mi:.2f}/100{mi_diff}\n"
        txt += f"Maintainability Grade:     {self._get_repo_grade(avg_mi)}{grade_diff}\n"
        txt += f"Technical Debt Score:      {self._get_repo_debt():.2f}/100{debt_diff}\n"
        txt += f"Total Findings:            {len(self.findings)}{findings_diff} (Critical/High: {sum(1 for f in self.findings if f['priority']=='High')}, Medium: {sum(1 for f in self.findings if f['priority']=='Medium')}, Low: {sum(1 for f in self.findings if f['priority']=='Low')})\n\n"
        
        txt += "AVERAGE CODE METRICS:\n"
        txt += f"  Average Complexity:      {avg_cc:.2f}{cc_diff}\n"
        txt += f"  Average Maintainability: {avg_mi:.2f}{mi_diff}\n"
        txt += f"  Average Function Length: {avg_func_len:.2f} LOC{func_len_diff}\n"
        txt += f"  Average Class Size:      {avg_class_len:.2f} LOC{class_size_diff}\n"
        txt += f"  Average File Size:       {avg_file_len:.2f} LOC{file_size_diff}\n\n"
        
        txt += "EXTREME HIGHLIGHTS:\n"
        txt += f"  Most Complex File:       {most_complex_file['file']} (Complexity: {most_complex_file['complexity']['cyclomatic']})\n"
        txt += f"  Largest File:            {largest_file['file']} ({largest_file['loc']} LOC)\n"
        txt += f"  Largest Class:           {largest_class['name']} ({largest_class['loc']} LOC)\n"
        txt += f"  Largest Function:        {largest_function['name']} ({largest_function['loc']} LOC)\n"
        txt += f"  Highest Risk Directory:  {highest_risk_dir}\n\n"
        
        txt += "TOP COMPLEX FILES:\n"
        txt += tabulate([[f['file'], f['complexity']['cyclomatic']] for f in top_complex], headers=["File Path", "Complexity"], tablefmt="grid") + "\n\n"
        txt += "TOP LARGEST FILES:\n"
        txt += tabulate([[f['file'], f['loc']] for f in top_largest], headers=["File Path", "LOC"], tablefmt="grid") + "\n\n"
        txt += "LOWEST MAINTAINABILITY FILES:\n"
        txt += tabulate([[f['file'], f['grade'], f"{f['maintainability_index']:.2f}"] for f in lowest_mi], headers=["File Path", "Grade", "Maintainability Index"], tablefmt="grid") + "\n"
        
        json_data = {
            "overall_quality_score": round(avg_mi, 2),
            "maintainability_grade": self._get_repo_grade(avg_mi),
            "technical_debt_score": round(self._get_repo_debt(), 2),
            "findings_summary": {"total": len(self.findings)},
            "averages": {
                "complexity": round(avg_cc, 2),
                "maintainability": round(avg_mi, 2),
                "function_length": round(avg_func_len, 2),
                "class_size": round(avg_class_len, 2),
                "file_size": round(avg_file_len, 2)
            },
            "highlights": {
                "most_complex_file": most_complex_file['file'],
                "largest_file": largest_file['file'],
                "largest_class": largest_class['name'],
                "largest_function": largest_function['name']
            }
        }
        self._write_files("01_quality_summary", txt, json_data)
        
    def _get_repo_grade(self, mi: float) -> str:
        if mi >= 80.0: return 'A'
        if mi >= 70.0: return 'B'
        if mi >= 60.0: return 'C'
        if mi >= 50.0: return 'D'
        return 'F'
        
    def _get_repo_debt(self) -> float:
        if not self.file_analyses: return 0.0
        return sum(f['technical_debt_score'] for f in self.file_analyses.values()) / len(self.file_analyses)
        
    def _report_02_complexity_analysis(self):
        txt = "====================================================\n"
        txt += "           02_COMPLEXITY_ANALYSIS REPORT            \n"
        txt += "====================================================\n\n"
        
        # Additional complexity calculations
        total_funcs = sum(len(f['functions']) for f in self.file_analyses.values())
        avg_nesting = sum(f['complexity']['nesting_depth'] for f in self.file_analyses.values()) / max(1, len(self.file_analyses))
        max_branches = max((fn['branches'] for f in self.file_analyses.values() for fn in f['functions']), default=0)
        max_loops = max((fn['loops'] for f in self.file_analyses.values() for fn in f['functions']), default=0)
        
        txt += f"Average Nesting Depth:       {avg_nesting:.2f}\n"
        txt += f"Maximum Branches / Function: {max_branches}\n"
        txt += f"Maximum Loops / Function:    {max_loops}\n\n"
        
        txt += "FILE COMPLEXITY RANKINGS:\n"
        file_metrics = []
        for rel_path, analysis in self.file_analyses.items():
            cc = analysis['complexity']
            prev_cc = self.prev_complexities.get(rel_path, {}).get('cyclomatic')
            cc_diff = self._get_diff_text(cc['cyclomatic'], prev_cc)
            file_metrics.append([
                rel_path, f"{cc['cyclomatic']}{cc_diff}", cc['cognitive'], cc['nesting_depth'],
                cc['decision_count'], cc['loop_count'], cc['branch_count'], cc['switch_count']
            ])
        file_metrics = sorted(file_metrics, key=lambda x: int(x[1].split(' ')[0]), reverse=True)
        txt += tabulate(file_metrics, headers=["File Path", "CC", "Cognitive", "Max Nest", "Decisions", "Loops", "Branches", "Switches"], tablefmt="grid") + "\n"
        
        json_data = {
            "average_nesting_depth": round(avg_nesting, 2),
            "max_branches_per_function": max_branches,
            "max_loops_per_function": max_loops,
            "file_complexities": [
                {
                    "file": f['file'],
                    "cyclomatic": f['complexity']['cyclomatic'],
                    "cognitive": f['complexity']['cognitive'],
                    "nesting_depth": f['complexity']['nesting_depth'],
                    "decision_count": f['complexity']['decision_count'],
                    "loop_count": f['complexity']['loop_count'],
                    "branch_count": f['complexity']['branch_count'],
                    "switch_count": f['complexity']['switch_count']
                } for f in self.file_analyses.values()
            ]
        }
        self._write_files("02_complexity_analysis", txt, json_data)
        
    def _report_03_function_analysis(self):
        txt = "====================================================\n"
        txt += "           03_FUNCTION_ANALYSIS REPORT              \n"
        txt += "====================================================\n\n"
        
        all_funcs = []
        for f in self.file_analyses.values():
            all_funcs.extend(f['functions'])
            
        if all_funcs:
            lengths = sorted([fn['loc'] for fn in all_funcs])
            median_len = lengths[len(lengths) // 2]
            shortest_fn = min(all_funcs, key=lambda x: x['loc'])
            longest_fn = max(all_funcs, key=lambda x: x['loc'])
            avg_returns = sum(fn['returns'] for fn in all_funcs) / len(all_funcs)
            undocumented = sum(1 for fn in all_funcs if not fn['doc_present'])
        else:
            median_len = 0
            shortest_fn = {'name': 'None', 'file': 'None', 'loc': 0}
            longest_fn = {'name': 'None', 'file': 'None', 'loc': 0}
            avg_returns = 0.0
            undocumented = 0
            
        txt += f"Median Function Length:      {median_len} LOC\n"
        txt += f"Longest Function:            {longest_fn['name']} in {longest_fn['file']} ({longest_fn['loc']} LOC)\n"
        txt += f"Shortest Function:           {shortest_fn['name']} in {shortest_fn['file']} ({shortest_fn['loc']} LOC)\n"
        txt += f"Average Return Statements:   {avg_returns:.2f}\n"
        txt += f"Undocumented Functions:      {undocumented}\n\n"
        
        funcs_table = []
        for fn in all_funcs:
            funcs_table.append([
                fn['name'], fn['file'], fn['start_line'], fn['loc'], fn['parameters'],
                fn['returns'], "Yes" if fn['is_pure'] else "No", "Yes" if fn['recursive'] else "No",
                "Yes" if fn['async'] else "No", "Yes" if fn['doc_present'] else "No"
            ])
            
        txt += tabulate(funcs_table, headers=["Function", "File Path", "Line", "LOC", "Params", "Returns", "Pure", "Recur", "Async", "Doc"], tablefmt="grid") + "\n"
        
        json_data = {
            "median_function_length": median_len,
            "undocumented_functions": undocumented,
            "functions": all_funcs
        }
        self._write_files("03_function_analysis", txt, json_data)
        
    def _report_04_class_analysis(self):
        txt = "====================================================\n"
        txt += "           04_CLASS_ANALYSIS REPORT                 \n"
        txt += "====================================================\n\n"
        
        all_classes = []
        for f in self.file_analyses.values():
            all_classes.extend(f['classes'])
            
        classes_table = []
        for cl in all_classes:
            class_type = "Normal"
            if cl['loc'] > 500: class_type = "God Class"
            elif cl['loc'] <= 15 and len(cl['attributes']) > 0 and len(cl['methods']) <= 1: class_type = "Data Class"
            elif len(cl['methods']) > 0 and cl['static_methods'] == len(cl['methods']): class_type = "Utility Class"
            elif len(cl['methods']) == 0: class_type = "Empty Class"
            
            # Compute method density
            method_density = len(cl['methods']) / max(1, cl['loc'])
            attribute_density = len(cl['attributes']) / max(1, cl['loc'])
            
            classes_table.append([
                cl['name'], cl['file'], cl['loc'], len(cl['methods']), len(cl['attributes']),
                cl['inheritance_depth'], cl['child_count'], class_type
            ])
            
        txt += tabulate(classes_table, headers=["Class Name", "File Path", "LOC", "Methods", "Attrs", "Inherit Depth", "Children", "Type"], tablefmt="grid") + "\n"
        
        json_data = {
            "classes": [c for c in all_classes]
        }
        for c in json_data['classes']:
            c.pop('methods', None)
        self._write_files("04_class_analysis", txt, json_data)
        
    def _report_05_dependency_analysis(self):
        txt = "====================================================\n"
        txt += "           05_DEPENDENCY_ANALYSIS REPORT            \n"
        txt += "====================================================\n\n"
        
        txt += "IMPORT FREQUENCY:\n"
        sorted_freq = sorted(self.import_frequencies.items(), key=lambda x: x[1], reverse=True)[:15]
        txt += tabulate(sorted_freq, headers=["Imported Module", "Frequency"], tablefmt="grid") + "\n\n"
        
        txt += "SHARED MODULES (Imported by >= 3 files):\n"
        for sm in self.shared_modules:
            txt += f"  - {sm}\n"
        if not self.shared_modules:
            txt += "  None detected.\n"
        txt += "\n"
        
        txt += "CIRCULAR DEPENDENCIES:\n"
        if self.circular_chains:
            for chain in self.circular_chains:
                txt += "  " + " -> ".join(chain) + "\n"
        else:
            txt += "  None detected.\n"
        txt += "\n"
        
        imports_table = []
        for rel_path, analysis in self.file_analyses.items():
            imp = analysis['imports']
            imports_table.append([
                rel_path, len(imp['internal']), len(imp['external']),
                len(imp['duplicates']), len(imp['unused']), len(imp['broken'])
            ])
        txt += tabulate(imports_table, headers=["File Path", "Internal", "External", "Duplicates", "Unused", "Broken"], tablefmt="grid") + "\n"
        
        json_data = {
            "import_frequencies": dict(sorted_freq),
            "shared_modules": self.shared_modules,
            "circular_dependencies": self.circular_chains
        }
        self._write_files("05_dependency_analysis", txt, json_data)
        
    def _report_06_duplication_analysis(self):
        txt = "====================================================\n"
        txt += "           06_DUPLICATION_ANALYSIS REPORT           \n"
        txt += "====================================================\n\n"
        
        txt += "DUPLICATE BLOCKS (Top 15):\n"
        dup_blocks_data = [[b['file_a'], b['line_a'], b['file_b'], b['line_b'], b['length']] for b in self.duplicate_blocks_list[:15]]
        txt += tabulate(dup_blocks_data, headers=["File A", "Line A", "File B", "Line B", "Length (lines)"], tablefmt="grid") + "\n\n"
        
        txt += "DUPLICATE FILES:\n"
        for df in self.duplicate_files_list:
            txt += f"  - {df['file_a']} is identical to {df['file_b']}\n"
        if not self.duplicate_files_list:
            txt += "  No identical duplicate files found.\n"
        txt += "\n"
        
        txt += "NEAR-DUPLICATE FILES (Similarity > 70%):\n"
        near_table = [[n['file_a'], n['file_b'], f"{n['similarity']*100:.1f}%"] for n in self.near_duplicate_files]
        txt += tabulate(near_table, headers=["File A", "File B", "Similarity %"], tablefmt="grid") + "\n\n"
        
        txt += "DUPLICATE CONSTANTS:\n"
        seen_consts = {}
        dup_consts = []
        for c in self.duplicate_constants_list:
            key = (c['name'], c['value'])
            if key not in seen_consts: seen_consts[key] = []
            seen_consts[key].append(c['file'])
        for key, files in seen_consts.items():
            if len(files) > 1:
                dup_consts.append([key[0], key[1], ", ".join(files)])
        txt += tabulate(dup_consts, headers=["Constant Name", "Value", "Files"], tablefmt="grid") + "\n"
        
        json_data = {
            "duplicate_blocks": self.duplicate_blocks_list,
            "duplicate_files": self.duplicate_files_list,
            "near_duplicate_files": self.near_duplicate_files,
            "duplicate_constants": dup_consts
        }
        self._write_files("06_duplication_analysis", txt, json_data)
        
    def _report_07_architecture_analysis(self):
        txt = "====================================================\n"
        txt += "           07_ARCHITECTURE_ANALYSIS REPORT          \n"
        txt += "====================================================\n\n"
        
        # Package metrics
        pkg_sizes = {}
        for rel_path, analysis in self.file_analyses.items():
            parent = str(Path(rel_path).parent)
            pkg_sizes[parent] = pkg_sizes.get(parent, 0) + analysis['loc']
            
        txt += "PACKAGE SIZES:\n"
        sorted_pkgs = sorted(pkg_sizes.items(), key=lambda x: x[1], reverse=True)
        txt += tabulate(sorted_pkgs, headers=["Package/Directory", "Total LOC"], tablefmt="grid") + "\n\n"
        
        txt += "UNUSED INTERNAL MODULES (Dead/Orphan Modules):\n"
        for m in self.unused_internal_modules:
            txt += f"  - {m}\n"
        if not self.unused_internal_modules:
            txt += "  None detected.\n"
        txt += "\n"
        
        # Layer violations
        violations = []
        for rel_path, analysis in self.file_analyses.items():
            source_layer = next((name for name, paths in LAYERS if any(x in rel_path for x in paths)), None)
            source_prio = 2 if source_layer == "core" else (1 if source_layer == "modules" else 0)
            if source_layer:
                for target_path in analysis['imports']['resolved_internal']:
                    target_layer = next((name for name, paths in LAYERS if any(x in target_path for x in paths)), None)
                    target_prio = 2 if target_layer == "core" else (1 if target_layer == "modules" else 0)
                    if target_layer and target_prio < source_prio:
                        violations.append([rel_path, target_path, source_layer, target_layer])
                        
        txt += "LAYER VIOLATIONS:\n"
        txt += tabulate(violations, headers=["Source File", "Target File", "Source Layer", "Target Layer"], tablefmt="grid") + "\n"
        
        json_data = {
            "package_sizes": dict(sorted_pkgs),
            "dead_modules": self.unused_internal_modules,
            "layer_violations": violations
        }
        self._write_files("07_architecture_analysis", txt, json_data)
        
    def _report_08_code_smells(self):
        txt = "====================================================\n"
        txt += "           08_CODE_SMELLS REPORT                    \n"
        txt += "====================================================\n\n"
        
        smells_table = []
        for finding in self.findings:
            if finding['category'] in ("Code Smell", "Naming Analysis"):
                smells_table.append([
                    finding['file'], finding['line'] or "N/A", finding['severity'],
                    finding['rule'], finding['reason']
                ])
                
        smells_table = sorted(smells_table, key=lambda x: SEVERITY_ORDER.get(x[2], 99))
        txt += tabulate(smells_table, headers=["File Path", "Line", "Severity", "Smell/Naming Type", "Details"], tablefmt="grid") + "\n"
        
        json_data = {
            "findings": self.findings
        }
        self._write_files("08_code_smells", txt, json_data)
        
    def _report_09_maintainability(self):
        txt = "====================================================\n"
        txt += "           09_MAINTAINABILITY REPORT                \n"
        txt += "====================================================\n\n"
        
        maintain_table = []
        for rel_path, analysis in self.file_analyses.items():
            prev_mi = self.prev_maintainability.get(rel_path, {}).get('maintainability_index')
            mi_diff = self._get_diff_text(analysis['maintainability_index'], prev_mi)
            prev_grade = self.prev_maintainability.get(rel_path, {}).get('grade')
            grade_diff = f" (was {prev_grade})" if prev_grade and prev_grade != analysis['grade'] else ""
            
            maintain_table.append([
                rel_path, f"{analysis['grade']}{grade_diff}", f"{analysis['maintainability_index']:.2f}{mi_diff}",
                f"{analysis['technical_debt_score']:.2f}"
            ])
        maintain_table = sorted(maintain_table, key=lambda x: float(x[2].split(' ')[0]))
        txt += tabulate(maintain_table, headers=["File Path", "Grade", "Maintainability Index", "Technical Debt Score"], tablefmt="grid") + "\n"
        
        json_data = {
            "maintainability": [
                {
                    "file": f['file'],
                    "grade": f['grade'],
                    "maintainability_index": round(f['maintainability_index'], 2),
                    "technical_debt_score": round(f['technical_debt_score'], 2)
                } for f in self.file_analyses.values()
            ]
        }
        self._write_files("09_maintainability", txt, json_data)
        
    def _report_10_scan_metadata(self):
        txt = "====================================================\n"
        txt += "           10_SCAN_METADATA REPORT                  \n"
        txt += "====================================================\n\n"
        
        total_files = len(self.file_analyses)
        total_funcs = sum(len(f['functions']) for f in self.file_analyses.values())
        total_classes = sum(len(f['classes']) for f in self.file_analyses.values())
        local_time = time.localtime(self.results.get('start_time', time.time()))
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
        
        metadata_table = [
            ["Scan ID", self.scan_id],
            ["Timestamp", timestamp_str],
            ["Duration (seconds)", f"{self.scan_duration:.4f}"],
            ["Files Analyzed", total_files],
            ["Functions Analyzed", total_funcs],
            ["Classes Analyzed", total_classes],
            ["Total Findings", len(self.findings)],
            ["Warnings", len(self.results.get('warnings', []))],
            ["Errors", len(self.results.get('errors', []))]
        ]
        txt += tabulate(metadata_table, tablefmt="plain") + "\n"
        
        json_data = {
            "scan_id": self.scan_id,
            "timestamp": timestamp_str,
            "duration_seconds": self.scan_duration,
            "files_analyzed": total_files,
            "functions_analyzed": total_funcs,
            "classes_analyzed": total_classes,
            "total_findings": len(self.findings),
            "warnings_count": len(self.results.get('warnings', [])),
            "errors_count": len(self.results.get('errors', []))
        }
        self._write_files("10_scan_metadata", txt, json_data)
