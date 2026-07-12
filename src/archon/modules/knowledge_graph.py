import os
import re
import json
import time
import math
import hashlib
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple
from tabulate import tabulate

from archon.core.parser import LANGUAGE_RULES, get_language_name
from archon.modules.code_metrics import format_size
from archon.modules.code_analysis import resolve_import_path, clean_file_content

# Node types and their aesthetic hex colors for the HTML canvas explorer
NODE_COLORS = {
    "Repository": "#2c3e50",
    "Folder": "#e67e22",
    "File": "#3498db",
    "Class": "#9b59b6",
    "Interface": "#8e44ad",
    "Enum": "#e74c3c",
    "Struct": "#c0392b",
    "Function": "#2ecc71",
    "Method": "#27ae60",
    "Constructor": "#1abc9c",
    "Variable": "#f1c40f",
    "Constant": "#f39c12",
    "Property": "#d35400",
    "API Endpoint": "#00d2d3",
    "Database Model": "#ff9f43",
    "Database Table": "#ee5253",
    "Configuration File": "#7f8c8d",
    "Environment Variable": "#95a5a6",
    "Dependency": "#10ac84",
    "Exception": "#ff4d4d",
    "Decorator": "#ff9ff3",
    "Namespace": "#54a0ff",
    "Test File": "#2e86de",
    "Resource": "#8395a7"
}

class KnowledgeGraphReporter:
    def __init__(self, results: Dict[str, Any], output_root: Path):
        self.results = results
        self.output_root = output_root
        self.root_path = Path(results['root_path']).resolve()
        self.scanned = results['files_scanned']
        self.ignored = results['files_ignored']
        self.scan_duration = results['scan_duration']
        self.scan_id = results.get('scan_id', 'N/A')

        self.nodes: List[Dict[str, Any]] = []
        self.edges: List[Dict[str, Any]] = []
        self.symbols: Dict[str, List[Any]] = {
            "classes": [], "interfaces": [], "enums": [], "structs": [],
            "functions": [], "methods": [], "constructors": [], "variables": [],
            "constants": [], "properties": [], "imports": [], "exports": [],
            "exceptions": [], "decorators": [], "namespaces": []
        }
        self.imports_data: Dict[str, Any] = {
            "internal_imports": [], "external_imports": [], "circular_imports": [],
            "unused_imports": [], "relative_imports": [], "import_frequency": {},
            "most_imported_modules": []
        }
        self.packages_data: Dict[str, Any] = {
            "hierarchy": {}, "files": [], "dependencies": [], "dependents": [],
            "coupling": {}, "exports": [], "imports": [], "relationship_graph": {}
        }
        self.dependencies_data: Dict[str, Any] = {
            "internal_dependencies": [], "external_dependencies": [],
            "transitive_dependencies": [], "dependency_depths": {}
        }
        self.apis_data: Dict[str, Any] = {
            "endpoints": [], "http_methods": {}, "controllers": [],
            "handlers": [], "middleware": [], "authentication": [],
            "models": [], "connected_services": []
        }
        self.database_data: Dict[str, Any] = {
            "tables": [], "collections": [], "models": [], "relationships": [],
            "read_operations": [], "write_operations": [], "delete_operations": [],
            "references": []
        }
        self.configurations_data: Dict[str, Any] = {
            "configuration_files": [], "environment_variables": [], "secrets_usage": [],
            "feature_flags": [], "configuration_references": [], "runtime_settings": []
        }
        self.statistics: Dict[str, Any] = {}

        from archon.modules.settings_manager import load_config
        self.config = load_config(self.root_path / "archon-config.json")

    def generate_reports(self):
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._run_analysis()
        self._write_outputs()

    def _add_node(self, node_id: str, node_type: str, label: str, attributes: Dict[str, Any]) -> str:
        # Prevent duplicates
        for node in self.nodes:
            if node['id'] == node_id:
                # Merge attributes if needed
                node['attributes'].update(attributes)
                return node_id
        self.nodes.append({
            "id": node_id,
            "type": node_type,
            "label": label,
            "attributes": attributes
        })
        return node_id

    def _add_edge(self, source: str, target: str, rel_type: str, attributes: Optional[Dict[str, Any]] = None) -> str:
        edge_id = f"edge_{source}_{target}_{rel_type}"
        for edge in self.edges:
            if edge['id'] == edge_id:
                return edge_id
        self.edges.append({
            "id": edge_id,
            "source": source,
            "target": target,
            "type": rel_type,
            "attributes": attributes or {}
        })
        return edge_id

    def _run_analysis(self):
        graph_cfg = self.config.get("knowledge_graph", {})
        include_classes = graph_cfg.get("include_classes", True)
        include_functions = graph_cfg.get("include_functions", True)
        include_dependencies = graph_cfg.get("include_dependencies", True)
        include_apis = graph_cfg.get("include_apis", True)
        include_database = graph_cfg.get("include_database", True)
        include_configurations = graph_cfg.get("include_configurations", True)

        all_scanned_files = [f['file'] for f in self.scanned]
        repo_name = self.root_path.name
        repo_node_id = "repository_root"
        inheritance_to_resolve = []
        
        # Add Repository Root Node
        self._add_node(repo_node_id, "Repository", repo_name, {
            "path": str(self.root_path),
            "scan_id": self.scan_id,
            "files_count": len(self.scanned)
        })

        # Step 1: Create Folders and Files Nodes & Containment Relationships
        visited_folders: Set[str] = set()
        for f in self.scanned:
            rel_path = f['file']
            file_path_obj = Path(rel_path)
            
            # File Node
            file_node_id = f"file_{rel_path}"
            self._add_node(file_node_id, "File", file_path_obj.name, {
                "path": rel_path,
                "language": f['language'],
                "extension": f['extension'],
                "size_bytes": f['size_bytes'],
                "loc": f['physical_loc'],
                "comment_lines": f['comment_lines']
            })

            # Check if file is a Test File
            is_test_file = "test" in file_path_obj.name.lower() or "tests" in file_path_obj.parts
            if is_test_file:
                self._add_node(file_node_id, "Test File", file_path_obj.name, {
                    "is_test_file": True
                })

            # Folders containment hierarchy
            parts = file_path_obj.parent.parts[:graph_cfg.get("max_depth", 10)]
            parent_id = repo_node_id
            current_rel_folder = ""
            for idx, part in enumerate(parts):
                if not part or part == ".":
                    continue
                current_rel_folder = str(Path(*parts[:idx+1]))
                folder_id = f"folder_{current_rel_folder}"
                
                if folder_id not in visited_folders:
                    self._add_node(folder_id, "Folder", part, {
                        "path": current_rel_folder
                    })
                    self._add_edge(parent_id, folder_id, "contains")
                    visited_folders.add(folder_id)
                parent_id = folder_id

            # Folder contains File
            self._add_edge(parent_id, file_node_id, "contains")
            self._add_edge(file_node_id, parent_id, "located_in")

        # Step 2: Traverse files and analyze contents statically
        import_frequency = {}
        resolved_dependencies_graph = {}
        all_functions_map = {}
        all_classes_map = {}

        total_files = len(self.scanned)
        import sys
        for idx, f in enumerate(self.scanned, 1):
            percent = (idx / total_files) * 100 if total_files > 0 else 0
            bar_length = 20
            filled_length = int(round(bar_length * idx / float(total_files))) if total_files > 0 else 0
            bar = '=' * filled_length + '-' * (bar_length - filled_length)
            sys.stdout.write(f"\r\033[96m[*]\033[0m Static Parsing: [{bar}] {percent:5.1f}% ({idx}/{total_files})")
            sys.stdout.flush()

            rel_path = f['file']
            file_node_id = f"file_{rel_path}"
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

            # Parse package structure (Namespace)
            package_name = "default"
            if lang_id == 'python':
                # Python package is folder hierarchy
                pkg_parts = Path(rel_path).parent.parts
                if pkg_parts and pkg_parts[0] != ".":
                    package_name = ".".join(pkg_parts)
            elif lang_id in ('java', 'kotlin'):
                match = re.search(r'^\s*package\s+([A-Za-z0-9_.]+);?', clean_content, re.MULTILINE)
                if match:
                    package_name = match.group(1)
            elif lang_id == 'cpp':
                match = re.search(r'\bnamespace\s+([A-Za-z0-9_]+)', clean_content)
                if match:
                    package_name = match.group(1)

            if package_name != "default":
                ns_id = f"namespace_{package_name}"
                self._add_node(ns_id, "Namespace", package_name, {"namespace": package_name})
                self._add_edge(file_node_id, ns_id, "belongs_to")
                self.symbols["namespaces"].append(package_name)

            # Parse imports
            if include_dependencies:
                imports_list = self._parse_imports_local(clean_lines, lang_id)
                resolved_internal = []
                for imp in imports_list:
                    import_frequency[imp] = import_frequency.get(imp, 0) + 1
                    resolved = resolve_import_path(imp, rel_path, all_scanned_files)
                    if resolved:
                        resolved_internal.append(resolved)
                        target_file_node = f"file_{resolved}"
                        self._add_edge(file_node_id, target_file_node, "imports")
                        self._add_edge(file_node_id, target_file_node, "depends_on")
                        self.imports_data["internal_imports"].append({"source": rel_path, "target": resolved, "import_statement": imp})
                    else:
                        # External Dependency
                        dep_node_id = f"dep_{imp}"
                        self._add_node(dep_node_id, "Dependency", imp, {"external": True})
                        self._add_edge(file_node_id, dep_node_id, "depends_on")
                        self.imports_data["external_imports"].append({"file": rel_path, "dependency": imp})
                resolved_dependencies_graph[rel_path] = resolved_internal
            else:
                resolved_dependencies_graph[rel_path] = []

            # Parse classes
            class_defs = []
            if include_classes:
                class_defs = self._parse_classes_local(clean_content, clean_lines, rel_path, lang_id)
                for c in class_defs:
                    class_node_id = f"class_{rel_path}_{c['name']}"
                    all_classes_map[c['name']] = class_node_id
                    
                    c_type = "Class"
                    if c.get('is_interface'):
                        c_type = "Interface"
                        self.symbols["interfaces"].append(c['name'])
                    elif c.get('is_enum'):
                        c_type = "Enum"
                        self.symbols["enums"].append(c['name'])
                    elif c.get('is_struct'):
                        c_type = "Struct"
                        self.symbols["structs"].append(c['name'])
                    else:
                        self.symbols["classes"].append(c['name'])

                    self._add_node(class_node_id, c_type, c['name'], {
                        "file": rel_path,
                        "start_line": c['start_line'],
                        "end_line": c['end_line'],
                        "parent_class": c['parent']
                    })
                    self._add_edge(file_node_id, class_node_id, "defines")
                    self._add_edge(class_node_id, file_node_id, "belongs_to")

                    # Inheritance/Extends relationships
                    if c['parent'] and c['parent'] != "None":
                        inheritance_to_resolve.append((class_node_id, c['parent']))

                    # Parse class properties/attributes
                    for attr in c.get('attributes', []):
                        attr_node_id = f"property_{rel_path}_{c['name']}_{attr}"
                        self._add_node(attr_node_id, "Property", attr, {"class": c['name'], "file": rel_path})
                        self._add_edge(class_node_id, attr_node_id, "defines")
                        self.symbols["properties"].append(attr)

            # Parse functions / methods
            if include_functions:
                func_defs = self._parse_functions_local(clean_content, clean_lines, rel_path, lang_id)
                for fn in func_defs:
                    fn_name = fn['name']
                    fn_node_id = f"function_{rel_path}_{fn_name}"
                    all_functions_map[fn_name] = fn_node_id

                    # Is it a method? Check if it is inside a class scope
                    parent_class = None
                    for c in class_defs:
                        if c['start_line'] <= fn['start_line'] <= c['end_line']:
                            parent_class = c['name']
                            break

                    if parent_class:
                        fn_type = "Method"
                        class_node_id = f"class_{rel_path}_{parent_class}"
                        self._add_node(fn_node_id, fn_type, fn_name, {
                            "class": parent_class,
                            "file": rel_path,
                            "start_line": fn['start_line'],
                            "end_line": fn['end_line'],
                            "parameters": fn['parameters']
                        })
                        self._add_edge(class_node_id, fn_node_id, "defines")
                        self.symbols["methods"].append(fn_name)
                        
                        # Check if constructor
                        if fn_name in ('__init__', 'constructor', '__construct') or fn_name == parent_class:
                            self._add_node(fn_node_id, "Constructor", fn_name, {})
                            self.symbols["constructors"].append(fn_name)
                    else:
                        fn_type = "Function"
                        self._add_node(fn_node_id, fn_type, fn_name, {
                            "file": rel_path,
                            "start_line": fn['start_line'],
                            "end_line": fn['end_line'],
                            "parameters": fn['parameters']
                        })
                        self._add_edge(file_node_id, fn_node_id, "defines")
                        self.symbols["functions"].append(fn_name)

                    # Decorators
                    decorators = re.findall(r'^\s*@([A-Za-z0-9_.]+)', clean_lines[max(0, fn['start_line']-2)])
                    for dec in decorators:
                        dec_node_id = f"decorator_{dec}"
                        self._add_node(dec_node_id, "Decorator", dec, {})
                        self._add_edge(dec_node_id, fn_node_id, "decorates")
                        self.symbols["decorators"].append(dec)

                    # Exceptions thrown / caught
                    throws_list = re.findall(r'\braise\s+([A-Za-z0-9_]+)\b|\bthrow\s+new\s+([A-Za-z0-9_]+)\b', clean_content[fn['start_line']-1:fn['end_line']])
                    for th in throws_list:
                        exc_name = th[0] or th[1]
                        if exc_name:
                            exc_id = f"exception_{exc_name}"
                            self._add_node(exc_id, "Exception", exc_name, {})
                            self._add_edge(fn_node_id, exc_id, "throws")
                            self.symbols["exceptions"].append(exc_name)

                    # Catches
                    catches_list = re.findall(r'\bexcept\s+([A-Za-z0-9_]+)\b|\bcatch\s*\(\s*([A-Za-z0-9_]+)\b', clean_content[fn['start_line']-1:fn['end_line']])
                    for ca in catches_list:
                        exc_name = ca[0] or ca[1]
                        if exc_name:
                            exc_id = f"exception_{exc_name}"
                            self._add_node(exc_id, "Exception", exc_name, {})
                            self._add_edge(fn_node_id, exc_id, "catches")
                            self.symbols["exceptions"].append(exc_name)

            # API Endpoints Extraction
            if include_apis:
                self._extract_apis(clean_content, clean_lines, rel_path, file_node_id)

            # Database Extraction (Models, tables, operations)
            if include_database:
                self._extract_database(clean_content, clean_lines, rel_path, file_node_id)

            # Configurations and Environment Variables
            if include_configurations:
                self._extract_config(clean_content, clean_lines, rel_path, file_node_id)

        sys.stdout.write("\n")
        sys.stdout.flush()

        # Step 3: Resolve Call Graph Relationships (Function calls Function)
        if include_functions:
            for idx, f in enumerate(self.scanned, 1):
                percent = (idx / total_files) * 100 if total_files > 0 else 0
                bar_length = 20
                filled_length = int(round(bar_length * idx / float(total_files))) if total_files > 0 else 0
                bar = '=' * filled_length + '-' * (bar_length - filled_length)
                sys.stdout.write(f"\r\033[96m[*]\033[0m Resolving Calls: [{bar}] {percent:5.1f}% ({idx}/{total_files})")
                sys.stdout.flush()

                rel_path = f['file']
                lang_id = f['lang_id']
                filepath = self.root_path / rel_path
                try:
                    content = filepath.read_text(encoding='utf-8')
                except Exception:
                    try:
                        content = filepath.read_text(encoding='latin-1')
                    except Exception:
                        continue
                clean_content, _, _ = clean_file_content(content, lang_id)
                clean_lines = clean_content.splitlines()

                func_defs = self._parse_functions_local(clean_content, clean_lines, rel_path, lang_id)
                for fn in func_defs:
                    fn_name = fn['name']
                    fn_node_id = f"function_{rel_path}_{fn_name}"
                    body_content = "\n".join(clean_lines[fn['start_line'] - 1 : fn['end_line']])

                    # Search body for function calls
                    for callee_name, callee_node_id in all_functions_map.items():
                        if callee_name != fn_name and f"{callee_name}(" in body_content:
                            self._add_edge(fn_node_id, callee_node_id, "calls")
                            self._add_edge(callee_node_id, fn_node_id, "called_by")

            sys.stdout.write("\n")
            sys.stdout.flush()

        # Resolve inheritance
        for child_id, parent_name in inheritance_to_resolve:
            if parent_name in all_classes_map:
                parent_id = all_classes_map[parent_name]
                self._add_edge(child_id, parent_id, "inherits")
                self._add_edge(child_id, parent_id, "extends")
            else:
                parent_id = f"class_external_{parent_name}"
                self._add_node(parent_id, "Class", parent_name, {"external": True})
                self._add_edge(child_id, parent_id, "inherits")
                self._add_edge(child_id, parent_id, "extends")

        # Filter nodes by min_node_connections (except repository root, files, folders to keep structural integrity)
        min_conns = graph_cfg.get("min_node_connections", 1)
        if min_conns > 0:
            conn_counts = {}
            for e in self.edges:
                conn_counts[e['source']] = conn_counts.get(e['source'], 0) + 1
                conn_counts[e['target']] = conn_counts.get(e['target'], 0) + 1
            
            self.nodes = [
                n for n in self.nodes 
                if n['type'] in ("Repository", "Folder", "File", "Test File") or conn_counts.get(n['id'], 0) >= min_conns
            ]

        # Defensive edge filter: remove edges where source or target is not in nodes
        node_ids = {n['id'] for n in self.nodes}
        self.edges = [e for e in self.edges if e['source'] in node_ids and e['target'] in node_ids]

        # Step 4: Circular Imports detection
        circular_imports_chains = self._find_dependency_cycles_local(resolved_dependencies_graph)
        self.imports_data["circular_imports"] = circular_imports_chains

        # Populate package/module metrics
        self._populate_packages_metrics(resolved_dependencies_graph)

        # Populate dependencies
        self._populate_dependencies(resolved_dependencies_graph)

        # Generate Graph Statistics
        self._compute_statistics()

    def _parse_imports_local(self, clean_lines: List[str], lang_id: str) -> List[str]:
        imports = []
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
        for line in clean_lines:
            for pat in patterns:
                for match in pat.finditer(line):
                    val = match.group(1).strip()
                    # Clean up
                    val = val.replace("'", "").replace('"', '').replace(';', '')
                    if "," in val:
                        imports.extend([v.strip() for v in val.split(',') if v.strip()])
                    else:
                        imports.append(val)
        return list(set(imports))

    def _parse_classes_local(self, clean_content: str, clean_lines: List[str], rel_path: str, lang_id: str) -> List[Dict[str, Any]]:
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

        def get_line_num(content, idx):
            return content[:idx].count('\n') + 1

        def find_brace_match(content, start):
            idx = content.find('{', start)
            if idx == -1: return -1
            stack = 1
            i = idx + 1
            n = len(content)
            while i < n:
                if content[i] == '{': stack += 1
                elif content[i] == '}':
                    stack -= 1
                    if stack == 0: return i
                i += 1
            return -1

        def get_py_scope(lines, start):
            def_line = lines[start]
            def_indent = len(def_line) - len(def_line.lstrip())
            end = start
            for j in range(start + 1, len(lines)):
                line = lines[j]
                if not line.strip(): continue
                if len(line) - len(line.lstrip()) <= def_indent:
                    break
                end = j
            return end + 1

        class_re = class_regexes.get(lang_id)
        if class_re:
            for match in class_re.finditer(clean_content):
                name = match.group(1)
                parent = match.group(2).strip() if len(match.groups()) > 1 and match.group(2) else "None"
                idx = match.start()
                start_line = get_line_num(clean_content, idx)
                if lang_id in ('python', 'yaml'):
                    end_line = get_py_scope(clean_lines, start_line - 1)
                else:
                    end_idx = find_brace_match(clean_content, idx)
                    end_line = get_line_num(clean_content, end_idx) if end_idx != -1 else len(clean_lines)

                # Find class attributes
                attributes = []
                for j in range(start_line - 1, end_line):
                    line = clean_lines[j]
                    if "=" in line and not line.strip().startswith(('def ', 'class ', 'fun ', 'function ')):
                        left_side = line.split("=")[0].strip()
                        if re.match(r'^[A-Za-z0-9_]+$', left_side):
                            attributes.append(left_side)

                classes.append({
                    "name": name,
                    "parent": parent,
                    "start_line": start_line,
                    "end_line": end_line,
                    "is_interface": "interface" in match.group(0),
                    "is_enum": "enum" in match.group(0),
                    "is_struct": "struct" in match.group(0),
                    "attributes": attributes
                })
        return classes

    def _parse_functions_local(self, clean_content: str, clean_lines: List[str], rel_path: str, lang_id: str) -> List[Dict[str, Any]]:
        functions = []
        func_regexes = {
            'python': re.compile(r'\bdef\s+([A-Za-z0-9_]+)\s*\(([^)]*)\)'),
            'brace_based': re.compile(r'\b([A-Za-z0-9_]+)\s*\(([^)]*)\)(?:\s*[^{]*)\s*\{'),
            'arrow': re.compile(r'\b(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:\async\s*)?\(([^)]*)\)\s*=>')
        }

        def get_line_num(content, idx):
            return content[:idx].count('\n') + 1

        def find_brace_match(content, start):
            idx = content.find('{', start)
            if idx == -1: return -1
            stack = 1
            i = idx + 1
            n = len(content)
            while i < n:
                if content[i] == '{': stack += 1
                elif content[i] == '}':
                    stack -= 1
                    if stack == 0: return i
                i += 1
            return -1

        def get_py_scope(lines, start):
            def_line = lines[start]
            def_indent = len(def_line) - len(def_line.lstrip())
            end = start
            for j in range(start + 1, len(lines)):
                line = lines[j]
                if not line.strip(): continue
                if len(line) - len(line.lstrip()) <= def_indent:
                    break
                end = j
            return end + 1

        matched = []
        if lang_id == 'python':
            for m in func_regexes['python'].finditer(clean_content):
                matched.append((m.group(1), m.group(2), m.start(), 'python'))
        elif lang_id in ('javascript', 'typescript', 'java', 'kotlin', 'dart', 'cpp', 'c', 'php'):
            keywords = {'if', 'while', 'for', 'switch', 'catch', 'lock', 'using', 'def', 'class'}
            for m in func_regexes['brace_based'].finditer(clean_content):
                name = m.group(1)
                if name not in keywords:
                    matched.append((name, m.group(2), m.start(), 'brace'))
            if lang_id in ('javascript', 'typescript'):
                for m in func_regexes['arrow'].finditer(clean_content):
                    matched.append((m.group(1), m.group(2), m.start(), 'arrow'))

        for name, params_str, idx, f_type in matched:
            start_line = get_line_num(clean_content, idx)
            if f_type == 'python':
                end_line = get_py_scope(clean_lines, start_line - 1)
            else:
                end_idx = find_brace_match(clean_content, idx)
                end_line = get_line_num(clean_content, end_idx) if end_idx != -1 else len(clean_lines)

            params = [p.strip() for p in params_str.split(',') if p.strip()]
            functions.append({
                "name": name,
                "start_line": start_line,
                "end_line": end_line,
                "parameters": len(params)
            })
        return functions

    def _extract_apis(self, clean_content: str, clean_lines: List[str], rel_path: str, file_node_id: str):
        # Scan for common patterns (Flask, Express, FastAPI, Spring Boot)
        # Python Flask/FastAPI: @app.get('/route') or @router.post('/route')
        api_decorators = re.findall(r'@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]', clean_content)
        for method, route in api_decorators:
            api_node_id = f"api_{method.upper()}_{route}"
            self._add_node(api_node_id, "API Endpoint", f"{method.upper()} {route}", {
                "route": route,
                "method": method.upper(),
                "file": rel_path
            })
            self._add_edge(file_node_id, api_node_id, "contains")
            self.apis_data["endpoints"].append({"route": route, "method": method.upper(), "file": rel_path})
            self.apis_data["http_methods"][method.upper()] = self.apis_data["http_methods"].get(method.upper(), 0) + 1

        # Express.js: app.get('/route', ...), router.post('/route', ...)
        express_routes = re.findall(r'\b(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*[\'"]([^\'"]+)[\'"]', clean_content)
        for method, route in express_routes:
            api_node_id = f"api_{method.upper()}_{route}"
            self._add_node(api_node_id, "API Endpoint", f"{method.upper()} {route}", {
                "route": route,
                "method": method.upper(),
                "file": rel_path
            })
            self._add_edge(file_node_id, api_node_id, "contains")
            self.apis_data["endpoints"].append({"route": route, "method": method.upper(), "file": rel_path})
            self.apis_data["http_methods"][method.upper()] = self.apis_data["http_methods"].get(method.upper(), 0) + 1

    def _extract_database(self, clean_content: str, clean_lines: List[str], rel_path: str, file_node_id: str):
        # Database operations & Models check
        # Look for DB Models: class User(db.Model) or class User(Base) or @Entity class User
        db_model_matches = re.findall(r'class\s+([A-Za-z0-9_]+)\s*\(\s*(?:db\.Model|Base|models\.Model)\s*\)', clean_content)
        for model in db_model_matches:
            db_node_id = f"db_model_{model}"
            self._add_node(db_node_id, "Database Model", model, {"file": rel_path})
            self._add_edge(file_node_id, db_node_id, "defines")
            self.database_data["models"].append({"model": model, "file": rel_path})

        # SQL Create tables: CREATE TABLE table_name
        create_table_matches = re.findall(r'\bCREATE\s+TABLE\s+([A-Za-z0-9_]+)\b', clean_content, re.IGNORECASE)
        for table in create_table_matches:
            db_node_id = f"db_table_{table}"
            self._add_node(db_node_id, "Database Table", table, {"file": rel_path})
            self._add_edge(file_node_id, db_node_id, "defines")
            self.database_data["tables"].append({"table": table, "file": rel_path})

        # DB operations check in code: db.session.add, insert, select, delete, update
        has_select = "select " in clean_content.lower() or "find(" in clean_content
        has_insert = "insert " in clean_content.lower() or "create(" in clean_content or "save(" in clean_content
        has_delete = "delete " in clean_content.lower() or "remove(" in clean_content
        
        if has_select:
            self.database_data["read_operations"].append(rel_path)
        if has_insert:
            self.database_data["write_operations"].append(rel_path)
        if has_delete:
            self.database_data["delete_operations"].append(rel_path)

    def _extract_config(self, clean_content: str, clean_lines: List[str], rel_path: str, file_node_id: str):
        # Configuration files
        ext = Path(rel_path).suffix.lower()
        if ext in ('.json', '.yaml', '.yml', '.toml', '.ini', '.env') or rel_path.endswith('config'):
            cfg_node_id = f"cfg_{rel_path}"
            self._add_node(cfg_node_id, "Configuration File", Path(rel_path).name, {"path": rel_path})
            self.configurations_data["configuration_files"].append(rel_path)
            
            # Map dependency: File configured_by Config File
            # (Just link Repository or target directory folder node)
            self._add_edge(file_node_id, cfg_node_id, "configured_by")

        # Environment variables: os.environ, process.env, getenv
        env_vars = re.findall(r'\bos\.environ\.get\(\s*[\'"]([A-Za-z0-9_]+)[\'"]\b|\bprocess\.env\.([A-Za-z0-9_]+)\b|\bgetenv\(\s*[\'"]([A-Za-z0-9_]+)[\'"]\b', clean_content)
        for m in env_vars:
            var_name = m[0] or m[1] or m[2]
            if var_name:
                var_node_id = f"env_{var_name}"
                self._add_node(var_node_id, "Environment Variable", var_name, {})
                self._add_edge(file_node_id, var_node_id, "reads")
                self.configurations_data["environment_variables"].append(var_name)

    def _find_dependency_cycles_local(self, graph: Dict[str, List[str]]) -> List[List[str]]:
        cycles = []
        visited = {}
        path = []

        def dfs(node):
            visited[node] = 1 # active
            path.append(node)
            for neighbor in graph.get(node, []):
                if neighbor not in visited:
                    dfs(neighbor)
                elif visited[neighbor] == 1:
                    idx = path.index(neighbor)
                    cycles.append(path[idx:] + [neighbor])
            path.pop()
            visited[node] = 2 # finished

        for node in graph:
            if node not in visited:
                dfs(node)
        return cycles

    def _populate_packages_metrics(self, dep_graph: Dict[str, List[str]]):
        # Divide files into packages based on their directories
        packages_files = {}
        for f in self.scanned:
            rel_path = f['file']
            pkg = str(Path(rel_path).parent)
            if pkg == ".": pkg = "root"
            if pkg not in packages_files:
                packages_files[pkg] = []
            packages_files[pkg].append(rel_path)

        self.packages_data["hierarchy"] = packages_files
        self.packages_data["files"] = list(packages_files.keys())

        # Coupling calculations: Afferent and Efferent coupling for each package
        coupling = {}
        for pkg, files in packages_files.items():
            efferent = 0 # internal imports pointing out of package
            afferent = 0 # external imports pointing into package
            
            for f in files:
                for target in dep_graph.get(f, []):
                    target_pkg = str(Path(target).parent)
                    if target_pkg == ".": target_pkg = "root"
                    if target_pkg != pkg:
                        efferent += 1

            for other_pkg, other_files in packages_files.items():
                if other_pkg == pkg: continue
                for f in other_files:
                    for target in dep_graph.get(f, []):
                        target_pkg = str(Path(target).parent)
                        if target_pkg == ".": target_pkg = "root"
                        if target_pkg == pkg:
                            afferent += 1

            instability = (efferent / (afferent + efferent)) if (afferent + efferent) > 0 else 0.0
            coupling[pkg] = {
                "afferent_coupling": afferent,
                "efferent_coupling": efferent,
                "instability": instability
            }
        self.packages_data["coupling"] = coupling

    def _populate_dependencies(self, dep_graph: Dict[str, List[str]]):
        internal = []
        external = []
        depths = {}

        max_depth_limit = self.config.get("knowledge_graph", {}).get("max_depth", 10)
        # Calculate depths from BFS
        for f in self.scanned:
            rel_path = f['file']
            # Depth defined as distance to root repository node or imports chain depth
            queue = [(rel_path, 0)]
            visited = {rel_path}
            max_d = 0
            while queue:
                curr, d = queue.pop(0)
                if d >= max_depth_limit:
                    continue
                max_d = max(max_d, d)
                for neighbor in dep_graph.get(curr, []):
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, d + 1))
            depths[rel_path] = max_d

        self.dependencies_data["internal_dependencies"] = self.imports_data["internal_imports"]
        self.dependencies_data["external_dependencies"] = self.imports_data["external_imports"]
        self.dependencies_data["dependency_depths"] = depths

    def _compute_statistics(self):
        total_nodes = len(self.nodes)
        total_edges = len(self.edges)
        
        node_types = {}
        for n in self.nodes:
            node_types[n['type']] = node_types.get(n['type'], 0) + 1

        rel_types = {}
        for e in self.edges:
            rel_types[e['type']] = rel_types.get(e['type'], 0) + 1

        avg_connections = total_edges / total_nodes if total_nodes > 0 else 0.0

        # Maximum connections (degree)
        degrees = {}
        for e in self.edges:
            degrees[e['source']] = degrees.get(e['source'], 0) + 1
            degrees[e['target']] = degrees.get(e['target'], 0) + 1
        max_connections = max(degrees.values()) if degrees else 0

        # Graph Density
        # D = E / (V * (V-1))
        density = total_edges / (total_nodes * (total_nodes - 1)) if total_nodes > 1 else 0.0

        # Connected Components (undirected BFS)
        adj = {}
        for n in self.nodes:
            adj[n['id']] = []
        for e in self.edges:
            adj[e['source']].append(e['target'])
            adj[e['target']].append(e['source'])

        visited = set()
        components = 0
        component_sizes = []
        
        for n in self.nodes:
            nid = n['id']
            if nid not in visited:
                components += 1
                comp_size = 0
                q = [nid]
                visited.add(nid)
                while q:
                    curr = q.pop(0)
                    comp_size += 1
                    for neighbor in adj[curr]:
                        if neighbor not in visited:
                            visited.add(neighbor)
                            q.append(neighbor)
                component_sizes.append(comp_size)

        disconnected_components = sum(1 for sz in component_sizes if sz == 1)

        # Most Connected Entities
        most_connected_files = []
        most_connected_classes = []
        most_connected_functions = []

        for n in self.nodes:
            nid = n['id']
            deg = degrees.get(nid, 0)
            if n['type'] == 'File':
                most_connected_files.append((n['label'], deg))
            elif n['type'] in ('Class', 'Interface', 'Enum', 'Struct'):
                most_connected_classes.append((n['label'], deg))
            elif n['type'] in ('Function', 'Method', 'Constructor'):
                most_connected_functions.append((n['label'], deg))

        most_connected_files.sort(key=lambda x: x[1], reverse=True)
        most_connected_classes.sort(key=lambda x: x[1], reverse=True)
        most_connected_functions.sort(key=lambda x: x[1], reverse=True)

        self.statistics = {
            "total_nodes": total_nodes,
            "total_relationships": total_edges,
            "node_types": node_types,
            "relationship_types": rel_types,
            "average_connections": avg_connections,
            "maximum_connections": max_connections,
            "graph_density": density,
            "graph_depth": max(self.dependencies_data["dependency_depths"].values()) if self.dependencies_data["dependency_depths"] else 0,
            "connected_components": components,
            "disconnected_components": disconnected_components,
            "most_connected_files": most_connected_files[:10],
            "most_connected_classes": most_connected_classes[:10],
            "most_connected_functions": most_connected_functions[:10],
            "largest_modules": sorted([(f['name'], f['physical_loc']) for f in self.scanned], key=lambda x: x[1], reverse=True)[:10],
            "largest_packages": sorted([(pkg, len(files)) for pkg, files in self.packages_data["hierarchy"].items()], key=lambda x: x[1], reverse=True)[:10]
        }

    def _write_outputs(self):
        # 1. graph_summary.json
        summary_data = {
            "repository_overview": {
                "name": self.root_path.name,
                "path": str(self.root_path),
                "scan_id": self.scan_id,
                "total_scanned_files": len(self.scanned)
            },
            "node_summary": self.statistics["node_types"],
            "relationship_summary": self.statistics["relationship_types"],
            "architecture_overview": {
                "total_components": self.statistics["connected_components"],
                "disconnected_modules": self.statistics["disconnected_components"]
            },
            "largest_modules": self.statistics["largest_modules"],
            "most_connected_files": self.statistics["most_connected_files"],
            "most_connected_classes": self.statistics["most_connected_classes"],
            "most_connected_functions": self.statistics["most_connected_functions"],
            "graph_health": {
                "circular_imports_count": len(self.imports_data["circular_imports"]),
                "coupling_instability_avg": sum(c["instability"] for c in self.packages_data["coupling"].values()) / len(self.packages_data["coupling"]) if self.packages_data["coupling"] else 0.0
            },
            "recommendations": self._generate_recommendations()
        }

        # Save JSON files
        self._write_json("graph_summary.json", summary_data)
        self._write_json("nodes.json", self.nodes)
        self._write_json("edges.json", self.edges)
        self._write_json("symbols.json", self.symbols)
        self._write_json("imports.json", self.imports_data)
        self._write_json("packages.json", self.packages_data)
        self._write_json("dependencies.json", self.dependencies_data)
        self._write_json("apis.json", self.apis_data)
        self._write_json("database.json", self.database_data)
        self._write_json("configurations.json", self.configurations_data)
        self._write_json("graph_statistics.json", self.statistics)

        # 2. graph_summary.txt
        self._write_txt_summary(summary_data)

        # 3. repository_map.md
        self._write_markdown_map()

    def _safe_write_text(self, filepath: Path, content: str):
        self.output_root.mkdir(parents=True, exist_ok=True)
        for i in range(5):
            try:
                filepath.write_text(content, encoding='utf-8')
                return
            except Exception:
                time.sleep(0.2)
        filepath.write_text(content, encoding='utf-8')

    def _write_json(self, name: str, data: Any):
        json_path = self.output_root / name
        self._safe_write_text(json_path, json.dumps(data, indent=2))

    def _generate_recommendations(self) -> List[str]:
        recs = []
        circ = len(self.imports_data["circular_imports"])
        if circ > 0:
            recs.append(f"Resolve {circ} circular import chains to improve modularity and reduce side-effects during code changes.")
        
        discon = self.statistics["disconnected_components"]
        if discon > 0:
            recs.append(f"Investigate {discon} disconnected files/modules; verify if they are dead code or unused legacy files.")

        density = self.statistics["graph_density"]
        if density > 0.15:
            recs.append("High graph density indicates tight coupling between files. Consider introducing interfaces or shared helpers to decouple modules.")

        return recs or ["Graph architecture looks clean with no major coupling or dependency issues detected."]

    def _write_txt_summary(self, summary: Dict[str, Any]):
        t = []
        t.append("================================================================================")
        t.append("                      ARCHON ONE KNOWLEDGE GRAPH REPORT                         ")
        t.append("================================================================================")
        t.append(f"Repository Name: {summary['repository_overview']['name']}")
        t.append(f"Repository Path: {summary['repository_overview']['path']}")
        t.append(f"Scan Duration:   {self.scan_duration:.4f} seconds")
        t.append(f"Scan ID:         {self.scan_id}")
        t.append("--------------------------------------------------------------------------------")
        t.append("\n[NODE SUMMARY]")
        for k, v in self.statistics["node_types"].items():
            t.append(f"  - {k:<25}: {v}")
            
        t.append("\n[RELATIONSHIP SUMMARY]")
        for k, v in self.statistics["relationship_types"].items():
            t.append(f"  - {k:<25}: {v}")

        t.append("\n[GRAPH TOPOLOGY METRICS]")
        t.append(f"  - Total Entities/Nodes    : {self.statistics['total_nodes']}")
        t.append(f"  - Total Relationships/Edges: {self.statistics['total_relationships']}")
        t.append(f"  - Average Node Connections: {self.statistics['average_connections']:.2f}")
        t.append(f"  - Maximum Node Connections: {self.statistics['maximum_connections']}")
        t.append(f"  - Graph Density            : {self.statistics['graph_density']:.4f}")
        t.append(f"  - Connected Components     : {self.statistics['connected_components']}")
        t.append(f"  - Disconnected Modules     : {self.statistics['disconnected_components']}")

        t.append("\n[LARGEST MODULES]")
        t.append(tabulate(self.statistics["largest_modules"], headers=["File", "LOC"], tablefmt="plain"))

        t.append("\n[MOST CONNECTED ENTITIES]")
        t.append(tabulate(self.statistics["most_connected_files"], headers=["File", "Connections"], tablefmt="plain"))

        t.append("\n[RECOMMENDATIONS]")
        for idx, rec in enumerate(summary["recommendations"], 1):
            t.append(f"  {idx}. {rec}")
        t.append("================================================================================")
        
        txt_path = self.output_root / "graph_summary.txt"
        self._safe_write_text(txt_path, "\n".join(t))

    def _write_markdown_map(self):
        md = []
        md.append(f"# Repository Map & Architecture Summary - {self.root_path.name}")
        md.append(f"\n*Scan ID: {self.scan_id} | Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}*")
        
        md.append("\n## Folder & Package Hierarchy")
        for pkg, files in self.packages_data["hierarchy"].items():
            md.append(f"\n### Package: `{pkg}`")
            for f in files:
                md.append(f"- `{f}`")

        md.append("\n## Graph Statistics & Architecture Metrics")
        md.append(f"- **Total Nodes**: {self.statistics['total_nodes']}")
        md.append(f"- **Total Edges**: {self.statistics['total_relationships']}")
        md.append(f"- **Graph Density**: {self.statistics['graph_density']:.4f}")
        md.append(f"- **Graph Depth**: {self.statistics['graph_depth']}")
        md.append(f"- **Average Connections**: {self.statistics['average_connections']:.2f}")

        md.append("\n## Circular Dependencies")
        circ = self.imports_data["circular_imports"]
        if circ:
            md.append("WARNING: Circular import loops detected:")
            for chain in circ:
                md.append(f"- {' -> '.join(chain)}")
        else:
            md.append("No circular imports detected. Modularity is optimal.")

        md.append("\n## Recommendations")
        for rec in self._generate_recommendations():
            md.append(f"- {rec}")

        md_path = self.output_root / "repository_map.md"
        self._safe_write_text(md_path, "\n".join(md))
