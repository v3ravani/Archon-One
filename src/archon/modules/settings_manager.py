import os
import json
import time
import webbrowser
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any

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
  "performance": {
    "max_worker_threads": 4,
    "max_memory_usage": 1024,
    "max_files": 10000,
    "max_scan_time": 600,
    "enable_cache": True,
    "cache_size": 1000,
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
  }
}

global_server = None
project_root_path = Path.cwd()

def load_config(config_path: Path) -> Dict[str, Any]:
    if config_path.exists():
        try:
            return json.loads(config_path.read_text(encoding='utf-8'))
        except Exception:
            pass
    # If missing or broken, write and return default values
    try:
        config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding='utf-8')
    except Exception:
        pass
    return dict(DEFAULT_CONFIG)

class SettingsHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Silence default terminal logs to keep output clean
        pass

    def do_GET(self):
        if self.path == '/':
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
            
        elif self.path == '/api/config':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            
            config_path = project_root_path / "archon-config.json"
            cfg = load_config(config_path)
            self.wfile.write(json.dumps(cfg).encode('utf-8'))
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path == '/api/config':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            try:
                new_cfg = json.loads(post_data.decode('utf-8'))
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
                
        elif self.path == '/api/config/reset':
            config_path = project_root_path / "archon-config.json"
            config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding='utf-8')
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(DEFAULT_CONFIG).encode('utf-8'))
            
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
