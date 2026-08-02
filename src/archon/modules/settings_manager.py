import os
import json
import time
import webbrowser
import threading
import shutil
import stat
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

def safe_remove_path(target_path: Path):
    if not target_path.exists():
        return
        
    def _make_writable(func, path, exc_info):
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
        except Exception:
            pass

    if target_path.is_dir():
        try:
            shutil.rmtree(target_path, onerror=_make_writable)
        except Exception:
            pass
            
        if target_path.exists():
            for p in list(target_path.rglob("*")):
                try:
                    os.chmod(p, stat.S_IWRITE)
                    if p.is_file() or p.is_symlink():
                        p.unlink(missing_ok=True)
                except Exception:
                    pass
            try:
                shutil.rmtree(target_path, ignore_errors=True)
            except Exception:
                pass
    else:
        try:
            os.chmod(target_path, stat.S_IWRITE)
            target_path.unlink(missing_ok=True)
        except Exception:
            pass

    if target_path.exists():
        raise PermissionError(f"Could not delete '{target_path.name}'. File or folder is locked or in use by another process.")

DEFAULT_CONFIG = {
  "general": {
    "project_name": "Archon One Project",
    "output_folder": "archon-one",
    "create_timestamp_folder": True,
    "default_scan_location": ".",
    "auto_load_previous_config": True,
    "auto_save_settings": True,
    "auto_open_report_folder": False,
    "enable_scan_summary": True,
    "max_scan_history": 10,
    "language_detection": "auto"
  },
  "modules": {
    "code_metrics": True,
    "security": True,
    "code_analysis": True,
    "contributor_analysis": True,
    "repository_intelligence": True,
    "knowledge_graph": True,
    "diagrams": True,
    "run_selected_only": False
  },
  "output": {
    "txt": True,
    "json": True,
    "md": True,
    "output_tables": "ASCII",
    "sort_reports_by": "Severity",
    "max_rows_per_report": 100,
    "show_empty_reports": False,
    "compress_reports": False,
    "overwrite_existing_reports": True
  },
  "ignore_rules": {
    "ignore_directories": ["node_modules", ".git", "venv", "build", "dist", "coverage"],
    "ignore_files": ["*.min.js", "*.log", "*.lock"],
    "ignore_extensions": ["png", "jpg", "gif", "pdf", "zip"],
    "ignore_hidden_files": True,
    "ignore_hidden_directories": True,
    "ignore_binary_files": True,
    "ignore_generated_files": True,
    "ignore_vendor_libraries": True,
    "ignore_test_files": False,
    "ignore_documentation": False,
    "ignore_empty_files": True,
    "ignore_large_files": True,
    "max_file_size": 10485760,
    "max_directory_depth": 20
  },
  "thresholds": {
    "max_function_length": 100,
    "max_class_length": 500,
    "max_file_length": 1000,
    "max_parameters": 5,
    "max_cyclomatic_complexity": 15,
    "max_cognitive_complexity": 15,
    "max_nesting_depth": 5,
    "max_line_length": 120,
    "max_duplicate_percentage": 5.0,
    "max_duplicate_lines": 10,
    "min_comment_density": 10.0,
    "min_maintainability_score": 50.0,
    "max_technical_debt_score": 50.0,
    "max_dependency_depth": 5,
    "max_import_count": 20,
    "large_file_warning": 2097152,
    "critical_file_size": 5242880,
    "max_folder_size": 104857600
  },
  "security": {
    "enable_secret_detection": True,
    "enable_config_scan": True,
    "enable_dependency_scan": True,
    "enable_credential_scan": True,
    "enable_dangerous_function_detection": True,
    "enable_hardcoded_ip_detection": True,
    "enable_base64_detection": True,
    "enable_weak_crypto_detection": True,
    "enable_regex_scan": True,
    "enable_environment_scan": True,
    "minimum_severity": "Low",
    "max_secret_length": 128,
    "ignore_example_secrets": True
  },
  "knowledge_graph": {
    "include_classes": True,
    "include_functions": True,
    "include_dependencies": True,
    "include_apis": True,
    "include_database": True,
    "include_configurations": True,
    "max_depth": 10,
    "min_node_connections": 1
  },
  "diagrams": {
    "include_mmd": True,
    "include_puml": True,
    "max_nodes": 50
  },
  "performance": {
    "max_worker_threads": 4,
    "max_memory_usage": 1024,
    "max_files": 10000,
    "max_scan_time": 600,
    "enable_cache": True,
    "cache_size": 1000,
    "fast_scan": False,
    "incremental_scan": False,
    "skip_unchanged_files": False,
    "lazy_loading": False,
    "scan_mode": "full"
  },
  "advanced": {
    "enable_debug_logs": False,
    "verbose_logging": False,
    "save_scan_logs": True,
    "auto_cleanup_old_reports": False,
    "cleanup_after_days": 30,
    "max_report_history": 50,
    "validate_config_before_scan": True
  },
  "profiles": {}
}

global_server = None
project_root_path = Path.cwd()

BUILTIN_COMMANDS = {"scan", "graph", "diagrams", "report", "config", "git", "about", "help", "version", "profiles"}

def validate_profile_name(name: str) -> tuple[bool, str]:
    if not isinstance(name, str):
        return False, "Profile name must be a string."
    name = name.strip()
    if not name:
        return False, "Profile name cannot be empty."
    import re
    if not re.match(r"^[a-zA-Z0-9_-]+$", name):
        return False, "Profile name can only contain letters, numbers, underscores, and hyphens."
    if name.lower() in BUILTIN_COMMANDS:
        return False, f"Profile name '{name}' conflicts with a built-in Archon command."
    return True, ""

def validate_profile_commands(commands: list, profile_name: str = None) -> tuple[bool, str]:
    if not isinstance(commands, list) or len(commands) == 0:
        return False, "Commands list cannot be empty."
    for cmd in commands:
        if not isinstance(cmd, str) or not cmd.strip():
            return False, "Commands list contains empty or invalid command strings."
        if profile_name:
            clean_cmd = cmd.strip()
            if clean_cmd == profile_name or clean_cmd == f"archon {profile_name}" or clean_cmd.startswith(f"archon {profile_name} "):
                return False, f"Command '{cmd}' creates a self-referential loop with profile '{profile_name}'."
    return True, ""

def validate_profile(name: str, commands: list, existing_profiles: dict = None) -> tuple[bool, str]:
    valid, msg = validate_profile_name(name)
    if not valid:
        return False, msg
    valid, msg = validate_profile_commands(commands, profile_name=name)
    if not valid:
        return False, msg

    # Cycle detection in command profiles
    if existing_profiles:
        all_profiles = dict(existing_profiles)
        all_profiles[name] = commands

        visited = set()
        stack = set()

        def dfs(curr):
            visited.add(curr)
            stack.add(curr)
            curr_cmds = all_profiles.get(curr, [])
            for c in curr_cmds:
                parts = c.strip().split()
                if not parts:
                    continue
                sub_cmd = parts[1] if parts[0].lower() == "archon" and len(parts) > 1 else parts[0]
                if sub_cmd in all_profiles:
                    if sub_cmd in stack:
                        return True
                    if sub_cmd not in visited:
                        if dfs(sub_cmd):
                            return True
            stack.remove(curr)
            return False

        if dfs(name):
            return False, f"Circular dependency detected in command profile '{name}'."

    return True, ""

def export_profiles(config: dict) -> dict:
    return {"profiles": config.get("profiles", {})}

def import_profiles(config: dict, imported_data: dict, overwrite: bool = True) -> tuple[dict, int, list]:
    raw_profiles = {}
    if isinstance(imported_data, dict):
        if "profiles" in imported_data and isinstance(imported_data["profiles"], dict):
            raw_profiles = imported_data["profiles"]
        elif "profiles" in imported_data and isinstance(imported_data["profiles"], list):
            for p in imported_data["profiles"]:
                if isinstance(p, dict) and "name" in p and "commands" in p:
                    raw_profiles[p["name"]] = p["commands"]
        else:
            raw_profiles = imported_data
    elif isinstance(imported_data, list):
        for p in imported_data:
            if isinstance(p, dict) and "name" in p and "commands" in p:
                raw_profiles[p["name"]] = p["commands"]

    existing = dict(config.get("profiles", {})) if not overwrite else {}
    errors = []
    imported_count = 0

    for name, cmds in raw_profiles.items():
        valid, msg = validate_profile(name, cmds, existing_profiles=existing)
        if valid:
            existing[name] = cmds
            imported_count += 1
        else:
            errors.append(f"Profile '{name}': {msg}")

    config["profiles"] = existing
    return config, imported_count, errors

def load_config(config_path: Path) -> Dict[str, Any]:
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text(encoding='utf-8'))
            if "profiles" not in cfg:
                cfg["profiles"] = {}
            return cfg
        except Exception:
            pass
    # If missing or broken, write and return default values
    try:
        config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding='utf-8')
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)

def get_reports_history(root_path: Path) -> List[Dict[str, Any]]:
    config_path = root_path / "archon-config.json"
    cfg = load_config(config_path)
    output_dir_name = cfg.get("general", {}).get("output_folder", "archon-one")
    out_path = root_path / output_dir_name
    
    scans = []
    if out_path.exists() and out_path.is_dir():
        candidates = [p for p in out_path.iterdir() if p.is_dir()]
        if not candidates and (out_path / "index.html").exists():
            candidates = [out_path]

        for cand in sorted(candidates, key=lambda x: x.stat().st_mtime if x.exists() else 0, reverse=True):
            index_path = cand / "index.html"
            has_index = index_path.exists()
            
            if not has_index and cand.is_dir():
                try:
                    from archon.core.unified_generator import generate_unified_html_report
                    gen_index = generate_unified_html_report(cand)
                    if gen_index and gen_index.exists():
                        index_path = gen_index
                        has_index = True
                except Exception:
                    pass

            main_report_url = None
            if has_index:
                main_report_url = str(index_path.relative_to(root_path)).replace("\\", "/")
            elif (cand / "01_metrics" / "report.html").exists():
                main_report_url = str((cand / "01_metrics" / "report.html").relative_to(root_path)).replace("\\", "/")

            files_count = 0
            total_loc = 0
            vulnerabilities_count = 0
            critical_vulns = 0
            health_score = 90
            health_grade = "A"
            tech_debt_hours = 0
            graph_nodes = 0
            diagrams_count = 0

            # 1. Metrics JSON
            m_file = cand / "01_metrics" / "01_repository_summary.json"
            if m_file.exists():
                try:
                    data = json.loads(m_file.read_text(encoding="utf-8"))
                    ov = data.get("repository_overview", {})
                    files_count = ov.get("supported_files", ov.get("total_files", 0))
                    total_loc = ov.get("physical_loc", ov.get("logical_loc", 0))
                except Exception:
                    pass

            # 2. Security JSON
            s_file = cand / "02_security" / "01_security_summary.json"
            if s_file.exists():
                try:
                    data = json.loads(s_file.read_text(encoding="utf-8"))
                    vulnerabilities_count = data.get("total_vulnerabilities", 0)
                    critical_vulns = data.get("severity_counts", {}).get("Critical", 0)
                except Exception:
                    pass

            # 3. Repository Intelligence JSON
            i_file = cand / "05_Repository_Intelligence" / "01_repository_intelligence.json"
            if not i_file.exists():
                i_file = cand / "05_Repository_Intelligence" / "01_repository_health_summary.json"
            if i_file.exists():
                try:
                    data = json.loads(i_file.read_text(encoding="utf-8"))
                    health_score = data.get("health_score", data.get("repository_health_score", 90))
                    health_grade = data.get("health_grade", data.get("grade", "A"))
                    tech_debt_hours = data.get("technical_debt_hours", 0)
                except Exception:
                    pass

            # 4. Knowledge Graph
            g_file = cand / "knowledge-graph" / "nodes.json"
            if g_file.exists():
                try:
                    graph_nodes = len(json.loads(g_file.read_text(encoding="utf-8")))
                except Exception:
                    pass

            # 5. Diagrams
            d_dir = cand / "07_Diagrams"
            if d_dir.exists() and d_dir.is_dir():
                diagrams_count = len(list(d_dir.glob("*")))

            mtime = cand.stat().st_mtime if cand.exists() else 0
            readable_time = time.strftime("%b %d, %Y - %H:%M:%S", time.localtime(mtime)) if mtime else "Unknown"

            scans.append({
                "folder_name": cand.name,
                "rel_path": str(cand.relative_to(root_path)).replace("\\", "/"),
                "report_url": main_report_url,
                "timestamp": readable_time,
                "mtime": mtime,
                "has_index": has_index,
                "health_score": health_score,
                "health_grade": health_grade,
                "files_count": files_count,
                "total_loc": total_loc,
                "vulnerabilities": vulnerabilities_count,
                "critical_vulns": critical_vulns,
                "tech_debt_hours": tech_debt_hours,
                "graph_nodes": graph_nodes,
                "diagrams_count": diagrams_count
            })

    return scans

def compare_scans(root_path: Path, rel_path1: str, rel_path2: str) -> Dict[str, Any]:
    dir1 = (root_path / rel_path1).resolve()
    dir2 = (root_path / rel_path2).resolve()
    dir1.relative_to(root_path.resolve())
    dir2.relative_to(root_path.resolve())
    
    def extract_metrics(cand: Path):
        mtime = cand.stat().st_mtime if cand.exists() else 0
        readable_time = time.strftime("%b %d, %Y - %H:%M:%S", time.localtime(mtime)) if mtime else "Unknown"
        metrics = {
            "folder_name": cand.name,
            "rel_path": str(cand.relative_to(root_path)).replace("\\", "/"),
            "timestamp": readable_time,
            "mtime": mtime,
            "files_count": 0,
            "total_loc": 0,
            "vulnerabilities": 0,
            "critical_vulns": 0,
            "high_vulns": 0,
            "health_score": 90,
            "health_grade": "A",
            "tech_debt_hours": 0,
            "graph_nodes": 0,
            "diagrams_count": 0,
            "has_index": (cand / "index.html").exists()
        }
        
        # 01_metrics
        m_file = cand / "01_metrics" / "01_repository_summary.json"
        if m_file.exists():
            try:
                data = json.loads(m_file.read_text(encoding="utf-8"))
                ov = data.get("repository_overview", {})
                metrics["files_count"] = ov.get("supported_files", ov.get("total_files", 0))
                metrics["total_loc"] = ov.get("physical_loc", ov.get("logical_loc", 0))
            except Exception:
                pass

        # 02_security
        s_file = cand / "02_security" / "01_security_summary.json"
        if s_file.exists():
            try:
                data = json.loads(s_file.read_text(encoding="utf-8"))
                metrics["vulnerabilities"] = data.get("total_vulnerabilities", 0)
                counts = data.get("severity_counts", {})
                metrics["critical_vulns"] = counts.get("Critical", 0)
                metrics["high_vulns"] = counts.get("High", 0)
            except Exception:
                pass

        # 05_intelligence
        i_file = cand / "05_Repository_Intelligence" / "01_repository_intelligence.json"
        if not i_file.exists():
            i_file = cand / "05_Repository_Intelligence" / "01_repository_health_summary.json"
        if i_file.exists():
            try:
                data = json.loads(i_file.read_text(encoding="utf-8"))
                metrics["health_score"] = data.get("health_score", data.get("repository_health_score", 90))
                metrics["health_grade"] = data.get("health_grade", data.get("grade", "A"))
                metrics["tech_debt_hours"] = data.get("technical_debt_hours", 0)
            except Exception:
                pass

        # knowledge-graph
        g_file = cand / "knowledge-graph" / "nodes.json"
        if g_file.exists():
            try:
                metrics["graph_nodes"] = len(json.loads(g_file.read_text(encoding="utf-8")))
            except Exception:
                pass

        # 07_Diagrams
        d_dir = cand / "07_Diagrams"
        if d_dir.exists() and d_dir.is_dir():
            metrics["diagrams_count"] = len(list(d_dir.glob("*")))

        return metrics

    m1 = extract_metrics(dir1)
    m2 = extract_metrics(dir2)

    if m1["mtime"] > m2["mtime"]:
        m1, m2 = m2, m1

    delta = {
        "files_count": m2["files_count"] - m1["files_count"],
        "total_loc": m2["total_loc"] - m1["total_loc"],
        "vulnerabilities": m2["vulnerabilities"] - m1["vulnerabilities"],
        "critical_vulns": m2["critical_vulns"] - m1["critical_vulns"],
        "health_score": m2["health_score"] - m1["health_score"],
        "tech_debt_hours": round(m2["tech_debt_hours"] - m1["tech_debt_hours"], 2),
        "graph_nodes": m2["graph_nodes"] - m1["graph_nodes"],
        "diagrams_count": m2["diagrams_count"] - m1["diagrams_count"]
    }

    return {
        "scan1": m1,
        "scan2": m2,
        "delta": delta
    }

def get_graph_data(root_path: Path) -> Dict[str, Any]:
    config_path = root_path / "archon-config.json"
    cfg = load_config(config_path)
    output_dir_name = cfg.get("general", {}).get("output_folder", "archon-one")
    out_path = root_path / output_dir_name

    search_dirs = []
    if out_path.exists() and out_path.is_dir():
        for p in [out_path / "knowledge-graph", out_path] + list(out_path.rglob("*")):
            if p.is_dir() and (p / "nodes.json").exists():
                search_dirs.append(p)

    target_dir = None
    if search_dirs:
        target_dir = sorted(search_dirs, key=lambda x: x.stat().st_mtime, reverse=True)[0]

    # If no report found, generate one automatically
    if not target_dir:
        try:
            from archon.core.scanner import RepositoryScanner
            from archon.modules.knowledge_graph import KnowledgeGraphReporter
            scanner = RepositoryScanner(root_path)
            results = scanner.scan()
            target_dir = out_path / "knowledge-graph"
            reporter = KnowledgeGraphReporter(results, target_dir)
            reporter.generate_reports()
        except Exception:
            pass

    if target_dir and (target_dir / "nodes.json").exists():
        try:
            nodes = json.loads((target_dir / "nodes.json").read_text(encoding="utf-8"))
            edges = json.loads((target_dir / "edges.json").read_text(encoding="utf-8"))

            def _read_opt(fname, default):
                p = target_dir / fname
                if p.exists():
                    try:
                        return json.loads(p.read_text(encoding="utf-8"))
                    except Exception:
                        pass
                return default

            files = _read_opt("files.json", [])
            folders = _read_opt("folders.json", [])
            classes = _read_opt("classes.json", [])
            functions = _read_opt("functions.json", [])
            dependencies = _read_opt("dependencies.json", [])
            call_graph = _read_opt("call-graph.json", [])
            api_endpoints = _read_opt("api-endpoints.json", [])
            metrics = _read_opt("metrics.json", {})
            diagnostics = _read_opt("diagnostics.json", [])

            existing_node_ids = {n["id"] for n in nodes if "id" in n}

            # Synthesize Class nodes if missing from nodes.json
            for c in classes:
                cid = f"class_{c.get('file', '')}_{c.get('name', '')}"
                if cid not in existing_node_ids:
                    nodes.append({
                        "id": cid,
                        "type": "Class",
                        "name": c.get("name", ""),
                        "label": c.get("name", ""),
                        "path": c.get("file", ""),
                        "start_line": c.get("start_line", 1),
                        "end_line": c.get("end_line", 1),
                        "attributes": c
                    })
                    existing_node_ids.add(cid)
                    if c.get("file"):
                        edges.append({
                            "id": f"edge_defines_{c['file']}_{c['name']}",
                            "source": f"file_{c['file']}",
                            "target": cid,
                            "type": "defines"
                        })

            # Synthesize Function nodes if missing from nodes.json
            for f in functions:
                fid = f"func_{f.get('file', '')}_{f.get('name', '')}"
                if fid not in existing_node_ids:
                    nodes.append({
                        "id": fid,
                        "type": "Function",
                        "name": f.get("name", ""),
                        "label": f.get("name", ""),
                        "path": f.get("file", ""),
                        "start_line": f.get("start_line", 1),
                        "end_line": f.get("end_line", 1),
                        "attributes": f
                    })
                    existing_node_ids.add(fid)
                    if f.get("file"):
                        edges.append({
                            "id": f"edge_defines_{f['file']}_{f['name']}",
                            "source": f"file_{f['file']}",
                            "target": fid,
                            "type": "defines"
                        })

            # Synthesize Dependency nodes if missing from nodes.json
            for d in dependencies:
                pkg_name = d.get("package_name", d.get("name", ""))
                did = f"dep_{pkg_name}"
                if did not in existing_node_ids:
                    nodes.append({
                        "id": did,
                        "type": "Dependency",
                        "name": pkg_name,
                        "label": pkg_name,
                        "path": pkg_name,
                        "attributes": d
                    })
                    existing_node_ids.add(did)

            # Synthesize API Endpoint nodes if missing from nodes.json
            for api in api_endpoints:
                method = api.get("method", "GET")
                route = api.get("route", "/")
                api_id = f"api_{method}_{route}"
                if api_id not in existing_node_ids:
                    nodes.append({
                        "id": api_id,
                        "type": "API Endpoint",
                        "name": f"{method} {route}",
                        "label": f"{method} {route}",
                        "path": api.get("file", ""),
                        "attributes": api
                    })
                    existing_node_ids.add(api_id)

            return {
                "nodes": nodes,
                "edges": edges,
                "metadata": _read_opt("metadata.json", {}),
                "files": files,
                "folders": folders,
                "classes": classes,
                "functions": functions,
                "dependencies": dependencies,
                "call_graph": call_graph,
                "api_endpoints": api_endpoints,
                "metrics": metrics,
                "diagnostics": diagnostics
            }
        except Exception:
            pass

    # Complete AST scanning fallback if target_dir is absent
    try:
        from archon.core.scanner import RepositoryScanner
        from archon.modules.knowledge_graph import KnowledgeGraphReporter
        scanner = RepositoryScanner(root_path)
        results = scanner.scan()
        reporter = KnowledgeGraphReporter(results, out_path / "knowledge-graph")
        reporter.generate_reports()
        return get_graph_data(root_path)
    except Exception:
        return {"nodes": [], "edges": [], "classes": [], "functions": [], "dependencies": [], "api_endpoints": []}

    return {"nodes": nodes, "edges": edges}

class SettingsHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default terminal logs to keep output clean
        pass

    def handle_one_request(self):
        try:
            super().handle_one_request()
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError, OSError):
            pass

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed_url = urlparse(self.path)
        clean_path = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        if clean_path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            
            # Read template settings.html
            template_path = Path(__file__).parent.parent / "templates" / "settings.html"
            if template_path.exists():
                html_content = template_path.read_bytes()
            else:
                html_content = b"<h1>Archon One Template settings.html missing</h1>"
            self.wfile.write(html_content)
            
        elif clean_path == '/api/config':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            config_path = project_root_path / "archon-config.json"
            cfg = load_config(config_path)
            self.wfile.write(json.dumps(cfg).encode('utf-8'))
        elif clean_path == '/api/profiles/export':
            config_path = project_root_path / "archon-config.json"
            cfg = load_config(config_path)
            profiles_data = export_profiles(cfg)
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Disposition', 'attachment; filename="archon-profiles.json"')
            self.end_headers()
            self.wfile.write(json.dumps(profiles_data, indent=2).encode('utf-8'))
        elif clean_path == '/api/vault/status':
            from archon.modules.vault import SecretVault
            vault = SecretVault(project_root_path)
            status_data = vault.get_status()
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(status_data).encode('utf-8'))
        elif clean_path == '/api/reports/history':
            history = get_reports_history(project_root_path)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(history).encode('utf-8'))
        elif clean_path == '/api/reports/view':
            target_rel = query_params.get("path", [""])[0]
            if not target_rel:
                self.send_error(400, "Missing path parameter")
                return
            target_file = (project_root_path / target_rel).resolve()
            try:
                # Security check: must be inside project_root_path
                target_file.relative_to(project_root_path.resolve())
            except ValueError:
                self.send_error(403, "Access denied")
                return

            if target_file.exists() and target_file.is_file():
                ext = target_file.suffix.lower()
                content_type = 'text/plain; charset=utf-8'
                if ext == '.html':
                    content_type = 'text/html; charset=utf-8'
                elif ext == '.json':
                    content_type = 'application/json'
                elif ext in ['.svg', '.svgz']:
                    content_type = 'image/svg+xml'

                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.end_headers()
                self.wfile.write(target_file.read_bytes())
            else:
                self.send_error(404, "Report file not found")
        elif clean_path == '/api/graph/data':
            graph_payload = get_graph_data(project_root_path)
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(graph_payload).encode('utf-8'))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/config':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                new_cfg = json.loads(post_data.decode('utf-8'))
                # Validate profiles if present
                if "profiles" in new_cfg and isinstance(new_cfg["profiles"], dict):
                    existing = {}
                    for p_name, p_cmds in new_cfg["profiles"].items():
                        valid, msg = validate_profile(p_name, p_cmds, existing_profiles=existing)
                        if not valid:
                            raise ValueError(f"Invalid profile '{p_name}': {msg}")
                        existing[p_name] = p_cmds

                config_path = project_root_path / "archon-config.json"
                config_path.write_text(json.dumps(new_cfg, indent=2), encoding='utf-8')
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success"}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif self.path == '/api/profiles/import':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                imported_data = json.loads(post_data.decode('utf-8'))
                config_path = project_root_path / "archon-config.json"
                cfg = load_config(config_path)
                
                cfg, count, errors = import_profiles(cfg, imported_data, overwrite=False)
                if errors and count == 0:
                    raise ValueError("; ".join(errors))
                    
                config_path.write_text(json.dumps(cfg, indent=2), encoding='utf-8')
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({
                    "status": "success",
                    "imported_count": count,
                    "errors": errors,
                    "profiles": cfg.get("profiles", {})
                }).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))
                
        elif self.path == '/api/config/reset':
            config_path = project_root_path / "archon-config.json"
            config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding='utf-8')
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(DEFAULT_CONFIG).encode('utf-8'))
            
        elif self.path == '/api/vault/init':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                password = payload.get("password", "")
                from archon.modules.vault import SecretVault
                vault = SecretVault(project_root_path)
                vault.init_vault(password)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": "Secret Vault initialized successfully."}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif self.path == '/api/vault/mask':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                password = payload.get("password", "")
                files = payload.get("files", [])
                from archon.modules.vault import SecretVault
                vault = SecretVault(project_root_path)
                
                masked = []
                errors = []
                for f in files:
                    try:
                        target_p = project_root_path / f
                        rel = vault.mask_file(target_p, password)
                        masked.append(rel)
                    except Exception as ex:
                        errors.append(f"{f}: {ex}")

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "masked": masked, "errors": errors}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif self.path == '/api/vault/unmask':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                password = payload.get("password", "")
                files = payload.get("files", [])
                from archon.modules.vault import SecretVault
                vault = SecretVault(project_root_path)
                
                unmasked = []
                errors = []
                for f in files:
                    try:
                        target_p = project_root_path / f
                        rel = vault.unmask_file(target_p, password)
                        unmasked.append(rel)
                    except Exception as ex:
                        errors.append(f"{f}: {ex}")

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "unmasked": unmasked, "errors": errors}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif self.path == '/api/vault/change-password':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                old_password = payload.get("old_password", "")
                new_password = payload.get("new_password", "")
                from archon.modules.vault import SecretVault
                vault = SecretVault(project_root_path)
                vault.change_password(old_password, new_password)
                
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": "Master password updated and protected files re-encrypted successfully."}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif self.path == '/api/reports/delete':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                target_rel = payload.get("path", "")
                if not target_rel:
                    raise ValueError("Path parameter is required.")

                target_dir = (project_root_path / target_rel).resolve()
                try:
                    target_dir.relative_to(project_root_path.resolve())
                except ValueError:
                    self.send_response(403)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "error", "error_code": "ERR_ACCESS_DENIED", "message": "Access denied: Path is outside workspace root."}).encode('utf-8'))
                    return

                if not target_dir.exists():
                    self.send_response(404)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({"status": "error", "error_code": "ERR_NOT_FOUND", "message": f"Target path '{target_rel}' does not exist on disk."}).encode('utf-8'))
                    return

                safe_remove_path(target_dir)

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "message": f"Scan history '{target_rel}' deleted successfully."}).encode('utf-8'))
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "error_code": "ERR_DELETE_FAILED", "message": str(e)}).encode('utf-8'))

        elif self.path == '/api/reports/compile':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                target_rel = payload.get("path", "")
                if not target_rel:
                    raise ValueError("Path parameter required.")

                target_dir = (project_root_path / target_rel).resolve()
                target_dir.relative_to(project_root_path.resolve())

                from archon.core.unified_generator import generate_unified_html_report
                index_file = generate_unified_html_report(target_dir)
                rel_index = str(index_file.relative_to(project_root_path.resolve())).replace("\\", "/")

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "report_url": rel_index}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif self.path == '/api/reports/compare':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                payload = json.loads(post_data.decode('utf-8'))
                rel1 = payload.get("path1", "")
                rel2 = payload.get("path2", "")
                if not rel1 or not rel2:
                    raise ValueError("path1 and path2 parameters required for comparison.")

                comp_data = compare_scans(project_root_path, rel1, rel2)
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "success", "comparison": comp_data}).encode('utf-8'))
            except Exception as e:
                self.send_response(400)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error", "message": str(e)}).encode('utf-8'))

        elif self.path == '/api/shutdown':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "shutdown_triggered"}).encode('utf-8'))
            
            # Shutdown loop in separate thread
            def kill():
                time.sleep(0.5)
                global global_server
                if global_server:
                    global_server.shutdown()
                    
            threading.Thread(target=kill).start()
        else:
            self.send_error(404)

def launch_settings_server(root_path: Path, port: int):
    global global_server, project_root_path
    project_root_path = root_path
    
    # Load or write default configuration beforehand
    load_config(root_path / "archon-config.json")
    
    server_address = ('127.0.0.1', port)
    global_server = HTTPServer(server_address, SettingsHTTPHandler)
    
    print(f"[*] Started Settings Manager on http://localhost:{port}")
    print("[*] Press Ctrl+C or click Shutdown Server in the UI to exit.")
    
    # Auto-open browser
    webbrowser.open(f"http://localhost:{port}")
    
    try:
        global_server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        print("[*] Settings Manager closed.")

