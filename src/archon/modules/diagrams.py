import json
import re
import time
from pathlib import Path
from typing import Dict, Any, Tuple

class DiagramsReporter:
    def __init__(self, results: Dict[str, Any], output_root: Path, config: Dict[str, Any] = None):
        self.results = results
        self.output_root = output_root
        self.config = config or {}
        self.root_path = Path(results.get('root_path', '.')).resolve()
        self.files = results.get('files_scanned', [])
        
        self.classes = []
        self.functions = []
        self.imports = {}
        self.internal_dependencies = {}
        self.external_dependencies = {}
        self.apis = []
        self.database_calls = {}
        self.config_files = []
        
        self._analyze()

    def _analyze(self):
        all_scanned_files = [f['file'].replace('\\', '/') for f in self.files]
        all_file_names = {Path(f).name: f for f in all_scanned_files}
        
        for f in self.files:
            rel_path = f['file'].replace('\\', '/')
            ext = f['extension'].lower()
            if ext in ('.json', '.yaml', '.yml', '.toml', '.ini', '.env', '.config'):
                self.config_files.append(rel_path)
        
        for f in self.files:
            rel_path = f['file'].replace('\\', '/')
            abs_path = self.root_path / rel_path
            lang_id = f.get('lang_id', '')
            
            content = ""
            if abs_path.exists():
                try:
                    content = abs_path.read_text(encoding='utf-8', errors='ignore')
                except Exception:
                    try:
                        content = abs_path.read_text(encoding='latin-1', errors='ignore')
                    except Exception:
                        pass
            
            if not content:
                continue
                
            lines = content.splitlines()
            
            file_imports = []
            if lang_id == 'python':
                for line in lines:
                    m1 = re.match(r'^\s*import\s+([\w\.]+)', line)
                    if m1:
                        file_imports.append(m1.group(1))
                    m2 = re.match(r'^\s*from\s+([\w\.]+)\s+import', line)
                    if m2:
                        file_imports.append(m2.group(1))
            elif lang_id in ('javascript', 'typescript'):
                for line in lines:
                    m1 = re.search(r'\bimport\s+.*\s+from\s+[\'"]([^\'"]+)[\'"]', line)
                    if m1:
                        file_imports.append(m1.group(1))
                    m2 = re.search(r'\brequire\s*\(\s*[\'"]([^\'"]+)[\'"]\s*\)', line)
                    if m2:
                        file_imports.append(m2.group(1))
            elif lang_id in ('java', 'kotlin'):
                for line in lines:
                    m = re.match(r'^\s*import\s+([\w\.]+)', line)
                    if m:
                        file_imports.append(m.group(1))
            elif lang_id in ('c', 'cpp'):
                for line in lines:
                    m = re.match(r'^\s*#include\s*["<]([^">]+)[">]', line)
                    if m:
                        file_imports.append(m.group(1))
            
            self.imports[rel_path] = file_imports
            
            resolved_internals = []
            externals = []
            for imp in file_imports:
                if imp.startswith('.'):
                    parent_dir = Path(rel_path).parent
                    try:
                        norm_imp = (parent_dir / imp).resolve().relative_to(self.root_path)
                        norm_str = norm_imp.as_posix()
                        if norm_str in all_scanned_files:
                            resolved_internals.append(norm_str)
                            continue
                    except Exception:
                        pass
                
                found_internal = False
                imp_parts = imp.replace('.', '/').lower()
                for sf in all_scanned_files:
                    sf_lower = sf.lower()
                    if imp_parts in sf_lower or sf_lower.endswith(imp_parts + ".py") or sf_lower.endswith(imp_parts + ".ts") or sf_lower.endswith(imp_parts + ".js"):
                        resolved_internals.append(sf)
                        found_internal = True
                        break
                        
                if not found_internal:
                    imp_base = imp.split('.')[-1]
                    if imp_base + ".py" in all_file_names:
                        resolved_internals.append(all_file_names[imp_base + ".py"])
                    elif imp_base + ".js" in all_file_names:
                        resolved_internals.append(all_file_names[imp_base + ".js"])
                    elif imp_base + ".ts" in all_file_names:
                        resolved_internals.append(all_file_names[imp_base + ".ts"])
                    else:
                        top_pkg = imp.split('.')[0] if '.' in imp else imp.split('/')[0]
                        externals.append(top_pkg)
            
            self.internal_dependencies[rel_path] = list(set(resolved_internals))
            self.external_dependencies[rel_path] = list(set(externals))
            
            if lang_id == 'python':
                class_matches = re.finditer(r'^\s*class\s+(\w+)(?:\(([^)]+)\))?:', content, re.MULTILINE)
                for cm in class_matches:
                    self.classes.append({
                        'name': cm.group(1),
                        'parent': cm.group(2) if cm.group(2) else None,
                        'file': rel_path
                    })
            elif lang_id in ('javascript', 'typescript', 'java', 'kotlin', 'cpp'):
                class_matches = re.finditer(r'\bclass\s+(\w+)(?:\s+extends\s+(\w+))?', content)
                for cm in class_matches:
                    self.classes.append({
                        'name': cm.group(1),
                        'parent': cm.group(2) if cm.group(2) else None,
                        'file': rel_path
                    })
                    
            if lang_id == 'python':
                func_matches = re.finditer(r'^\s*def\s+(\w+)\s*\(([^)]*)\):', content, re.MULTILINE)
                for fm in func_matches:
                    self.functions.append({
                        'name': fm.group(1),
                        'params': fm.group(2),
                        'file': rel_path
                    })
            elif lang_id in ('javascript', 'typescript'):
                func_matches = re.finditer(r'\bfunction\s+(\w+)\s*\(([^)]*)\)', content)
                for fm in func_matches:
                    self.functions.append({
                        'name': fm.group(1),
                        'params': fm.group(2),
                        'file': rel_path
                    })
            elif lang_id in ('java', 'kotlin', 'cpp'):
                func_matches = re.finditer(r'\b(?:public|protected|private|static|\s) +[\w<>\[\]]+ +(\w+) *\(([^)]*)\) *\{', content)
                for fm in func_matches:
                    self.functions.append({
                        'name': fm.group(1),
                        'params': fm.group(2),
                        'file': rel_path
                    })
            
            if lang_id == 'python':
                api_matches = re.finditer(r'@(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', content)
                for am in api_matches:
                    self.apis.append({
                        'method': am.group(1).upper(),
                        'path': am.group(2),
                        'file': rel_path,
                        'type': 'HTTP Endpoint'
                    })
                if 'typer.Argument' in content or 'typer.Option' in content or 'click.command' in content:
                    self.apis.append({
                        'method': 'CLI',
                        'path': f"Command: {Path(rel_path).stem}",
                        'file': rel_path,
                        'type': 'CLI Interface'
                    })
            elif lang_id in ('javascript', 'typescript'):
                api_matches = re.finditer(r'\b(?:app|router)\.(get|post|put|delete|patch)\s*\(\s*["\']([^"\']+)["\']', content)
                for am in api_matches:
                    self.apis.append({
                        'method': am.group(1).upper(),
                        'path': am.group(2),
                        'file': rel_path,
                        'type': 'HTTP Endpoint'
                    })
            elif lang_id in ('java', 'kotlin'):
                api_matches = re.finditer(r'@(?:Get|Post|Put|Delete)Mapping\s*\(\s*value\s*=\s*["\']([^"\']+)["\']', content)
                for am in api_matches:
                    self.apis.append({
                        'method': 'API',
                        'path': am.group(1),
                        'file': rel_path,
                        'type': 'Spring Mapping'
                    })
            
            db_keywords = ['select ', 'insert into', 'update ', 'delete from', 'sqlalchemy', 'pymongo', 'sqlite3', 'db.model', 'db.execute']
            found_db = []
            content_lower = content.lower()
            for kw in db_keywords:
                if kw in content_lower:
                    found_db.append(kw.strip())
            if found_db:
                self.database_calls[rel_path] = list(set(found_db))

    def generate_architecture(self) -> Tuple[str, str]:
        mmd = "flowchart TB\n"
        mmd += "    subgraph Entry [Entry Points]\n"
        entry_nodes = []
        for f in self.files:
            rel = f['file'].replace('\\', '/')
            if Path(rel).parent == Path('.') or 'cli' in rel.lower() or 'main' in rel.lower():
                name = Path(rel).name
                entry_nodes.append((rel, name))
                mmd += f"        E_{hash(rel)%10000}[\"{name}\"]\n"
        mmd += "    end\n\n"
        
        mmd += "    subgraph Core [Core Engine]\n"
        core_nodes = []
        for f in self.files:
            rel = f['file'].replace('\\', '/')
            if 'core' in rel.lower() or 'engine' in rel.lower() or 'parser' in rel.lower() or 'scanner' in rel.lower():
                if (rel, Path(rel).name) not in entry_nodes:
                    name = Path(rel).name
                    core_nodes.append((rel, name))
                    mmd += f"        C_{hash(rel)%10000}[\"{name}\"]\n"
        mmd += "    end\n\n"
        
        mmd += "    subgraph Modules [Modules & Features]\n"
        module_nodes = []
        for f in self.files:
            rel = f['file'].replace('\\', '/')
            if 'modules' in rel.lower() or 'services' in rel.lower() or 'controllers' in rel.lower() or 'reporters' in rel.lower():
                if (rel, Path(rel).name) not in entry_nodes and (rel, Path(rel).name) not in core_nodes:
                    name = Path(rel).name
                    module_nodes.append((rel, name))
                    mmd += f"        M_{hash(rel)%10000}[\"{name}\"]\n"
        mmd += "    end\n\n"
        
        for e_rel, e_name in entry_nodes:
            for c_rel, c_name in core_nodes:
                if c_rel in self.internal_dependencies.get(e_rel, []):
                    mmd += f"    E_{hash(e_rel)%10000} --> C_{hash(c_rel)%10000}\n"
            for m_rel, m_name in module_nodes:
                if m_rel in self.internal_dependencies.get(e_rel, []):
                    mmd += f"    E_{hash(e_rel)%10000} --> M_{hash(m_rel)%10000}\n"
                    
        for c_rel, c_name in core_nodes:
            for m_rel, m_name in module_nodes:
                if m_rel in self.internal_dependencies.get(c_rel, []):
                    mmd += f"    C_{hash(c_rel)%10000} --> M_{hash(m_rel)%10000}\n"
                if c_rel in self.internal_dependencies.get(m_rel, []):
                    mmd += f"    M_{hash(m_rel)%10000} --> C_{hash(c_rel)%10000}\n"

        if not entry_nodes and not core_nodes and not module_nodes:
            for idx, f in enumerate(self.files[:10]):
                rel = f['file'].replace('\\', '/')
                name = Path(rel).name
                mmd += f"    F_{hash(rel)%10000}[\"{name}\"]\n"

        puml = "@startuml\n"
        puml += "title Overall Repository Architecture\n\n"
        puml += "package \"Entry Points\" {\n"
        for rel, name in entry_nodes:
            puml += f"  [{name}] as E_{hash(rel)%10000}\n"
        puml += "}\n\n"
        puml += "package \"Core Engine\" {\n"
        for rel, name in core_nodes:
            puml += f"  [{name}] as C_{hash(rel)%10000}\n"
        puml += "}\n\n"
        puml += "package \"Modules & Features\" {\n"
        for rel, name in module_nodes:
            puml += f"  [{name}] as M_{hash(rel)%10000}\n"
        puml += "}\n\n"
        
        for e_rel, e_name in entry_nodes:
            for c_rel, c_name in core_nodes:
                if c_rel in self.internal_dependencies.get(e_rel, []):
                    puml += f"E_{hash(e_rel)%10000} --> C_{hash(c_rel)%10000}\n"
            for m_rel, m_name in module_nodes:
                if m_rel in self.internal_dependencies.get(e_rel, []):
                    puml += f"E_{hash(e_rel)%10000} --> M_{hash(m_rel)%10000}\n"
        for c_rel, c_name in core_nodes:
            for m_rel, m_name in module_nodes:
                if m_rel in self.internal_dependencies.get(c_rel, []):
                    puml += f"C_{hash(c_rel)%10000} --> M_{hash(m_rel)%10000}\n"
                if c_rel in self.internal_dependencies.get(m_rel, []):
                    puml += f"M_{hash(m_rel)%10000} --> C_{hash(c_rel)%10000}\n"
        if not entry_nodes and not core_nodes and not module_nodes:
            for idx, f in enumerate(self.files[:10]):
                rel = f['file'].replace('\\', '/')
                name = Path(rel).name
                puml += f"  [{name}] as F_{hash(rel)%10000}\n"
        puml += "@endum\n"
        
        return mmd, puml

    def generate_component_diagram(self) -> Tuple[str, str]:
        mmd = "flowchart TD\n"
        mmd += "    Controller[Controllers & CLI]\n"
        mmd += "    Service[Services & Business Logic]\n"
        mmd += "    Repository[Repositories & DB Models]\n"
        mmd += "    Database[(Database)]\n"
        mmd += "    Utility[Utilities & Helpers]\n"
        mmd += "    Config[Configurations]\n\n"
        
        mmd += "    Controller --> Service\n"
        mmd += "    Service --> Repository\n"
        mmd += "    Service --> Utility\n"
        mmd += "    Service --> Config\n"
        mmd += "    Repository --> Database\n"
        
        puml = "@startuml\n"
        puml += "title Component Diagram\n\n"
        puml += "node \"Controllers & CLI\" as Controller\n"
        puml += "node \"Services & Business Logic\" as Service\n"
        puml += "node \"Repositories & DB Models\" as Repository\n"
        puml += "database \"Database\" as Database\n"
        puml += "node \"Utilities & Helpers\" as Utility\n"
        puml += "node \"Configurations\" as Config\n\n"
        puml += "Controller --> Service\n"
        puml += "Service --> Repository\n"
        puml += "Service --> Utility\n"
        puml += "Service --> Config\n"
        puml += "Repository --> Database\n"
        puml += "@endum\n"
        
        return mmd, puml

    def generate_module_diagram(self) -> Tuple[str, str]:
        modules = set()
        for f in self.files:
            rel = f['file'].replace('\\', '/')
            parts = Path(rel).parent.parts
            if parts and parts[0] != '.':
                modules.add(parts[0])
            else:
                modules.add('root')
                
        mmd = "flowchart TB\n"
        puml = "@startuml\ntitle Module Diagram\n\n"
        
        for m in sorted(list(modules)):
            mmd += f"    Mod_{m}[\"{m.upper()} Module\"]\n"
            puml += f"package \"{m.upper()} Module\" as Mod_{m} {{\n}}\n"
            
        for f in self.files:
            rel = f['file'].replace('\\', '/')
            f_parts = Path(rel).parent.parts
            f_mod = f_parts[0] if f_parts and f_parts[0] != '.' else 'root'
            
            for dep in self.internal_dependencies.get(rel, []):
                d_parts = Path(dep).parent.parts
                d_mod = d_parts[0] if d_parts and d_parts[0] != '.' else 'root'
                
                if f_mod != d_mod:
                    mmd += f"    Mod_{f_mod} --> Mod_{d_mod}\n"
                    puml += f"Mod_{f_mod} --> Mod_{d_mod}\n"
                    
        puml += "@endum\n"
        
        mmd_lines = list(set(mmd.splitlines()))
        puml_lines = list(set(puml.splitlines()))
        
        mmd_final = "flowchart TB\n" + "\n".join(l for l in mmd_lines if "Mod_" in l)
        puml_final = "@startuml\ntitle Module Diagram\n\n" + "\n".join(l for l in puml_lines if "package" in l or "Mod_" in l) + "\n@endum\n"
        return mmd_final, puml_final

    def generate_package_diagram(self) -> Tuple[str, str]:
        packages = {}
        for f in self.files:
            rel = f['file'].replace('\\', '/')
            parent = str(Path(rel).parent).replace('\\', '/')
            if parent == '.':
                parent = 'root'
            if parent not in packages:
                packages[parent] = []
            packages[parent].append(Path(rel).name)
            
        mmd = "flowchart TB\n"
        puml = "@startuml\ntitle Package Diagram\n\n"
        
        for pkg, files in packages.items():
            pkg_id = pkg.replace('/', '_').replace('.', '_')
            mmd += f"    subgraph Sub_{pkg_id} [Package: {pkg}]\n"
            puml += f"package \"{pkg}\" {{\n"
            for f_name in files[:5]:
                f_id = f_name.replace('.', '_')
                mmd += f"        File_{pkg_id}_{f_id}[\"{f_name}\"]\n"
                puml += f"  [{f_name}] as File_{pkg_id}_{f_id}\n"
            mmd += "    end\n\n"
            puml += "}\n\n"
            
        for f in self.files:
            rel = f['file'].replace('\\', '/')
            f_pkg = str(Path(rel).parent).replace('\\', '/').replace('.', '_').replace('/', '_')
            if f_pkg == '': f_pkg = 'root'
            f_id = Path(rel).name.replace('.', '_')
            
            for dep in self.internal_dependencies.get(rel, []):
                d_pkg = str(Path(dep).parent).replace('\\', '/').replace('.', '_').replace('/', '_')
                if d_pkg == '': d_pkg = 'root'
                d_id = Path(dep).name.replace('.', '_')
                
                if f_pkg != d_pkg:
                    mmd += f"    File_{f_pkg}_{f_id} --> File_{d_pkg}_{d_id}\n"
                    puml += f"File_{f_pkg}_{f_id} --> File_{d_pkg}_{d_id}\n"
                    
        puml += "@endum\n"
        return mmd, puml

    def generate_dependency_diagram(self) -> Tuple[str, str]:
        max_nodes = self.config.get("diagrams", {}).get("max_nodes", 50)
        graph = {}
        for f in self.files:
            rel = f['file'].replace('\\', '/')
            graph[rel] = self.internal_dependencies.get(rel, [])
            
        visited = {}
        path = []
        cycles = []
        
        def dfs(node):
            if node in visited:
                if visited[node] == 1:
                    cycle_start = path.index(node)
                    cycles.append(path[cycle_start:] + [node])
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
                
        fan_in = {}
        for node, neighbors in graph.items():
            for neighbor in neighbors:
                fan_in[neighbor] = fan_in.get(neighbor, 0) + 1
                
        shared_modules = [node for node, count in fan_in.items() if count >= 3]
        
        mmd = "flowchart LR\n"
        displayed_files = [f['file'].replace('\\', '/') for f in self.files[:max_nodes]]
        
        for f in displayed_files:
            name = Path(f).name
            node_id = f"Dep_{hash(f)%10000}"
            if f in shared_modules:
                mmd += f"    {node_id}[\"{name} (Shared)\"]:::shared\n"
            else:
                mmd += f"    {node_id}[\"{name}\"]\n"
                
        lines = []
        for src in displayed_files:
            src_id = f"Dep_{hash(src)%10000}"
            for tgt in self.internal_dependencies.get(src, []):
                if tgt in displayed_files:
                    tgt_id = f"Dep_{hash(tgt)%10000}"
                    
                    is_circular = False
                    for cycle in cycles:
                        for idx in range(len(cycle)-1):
                            if cycle[idx] == src and cycle[idx+1] == tgt:
                                is_circular = True
                                break
                    if is_circular:
                        lines.append(f"    {src_id} -- Circular --> {tgt_id}")
                    else:
                        lines.append(f"    {src_id} --> {tgt_id}")
                        
        mmd += "\n".join(list(set(lines))) + "\n"
        mmd += "    classDef shared fill:#e8f5e9,stroke:#4CAF50,stroke-width:2px;\n"
        mmd += "    classDef circular stroke:#E53935,stroke-width:2px;\n"
        
        puml = "@startuml\ntitle Dependency Diagram\n\n"
        for f in displayed_files:
            name = Path(f).name
            node_id = f"Dep_{hash(f)%10000}"
            if f in shared_modules:
                puml += f"[{name}] as {node_id} #line:green;line.bold\n"
            else:
                puml += f"[{name}] as {node_id}\n"
                
        lines_puml = []
        for src in displayed_files:
            src_id = f"Dep_{hash(src)%10000}"
            for tgt in self.internal_dependencies.get(src, []):
                if tgt in displayed_files:
                    tgt_id = f"Dep_{hash(tgt)%10000}"
                    is_circular = False
                    for cycle in cycles:
                        for idx in range(len(cycle)-1):
                            if cycle[idx] == src and cycle[idx+1] == tgt:
                                is_circular = True
                                break
                    if is_circular:
                        lines_puml.append(f"{src_id} -[#red,bold]-> {tgt_id} : Circular")
                    else:
                        lines_puml.append(f"{src_id} --> {tgt_id}")
        puml += "\n".join(list(set(lines_puml))) + "\n@endum\n"
        
        return mmd, puml

    def generate_folder_structure(self) -> Tuple[str, str]:
        visited_folders = set()
        mmd = "flowchart LR\n"
        mmd += "    Root[\"Repository Root\"]\n"
        puml = "@startuml\ntitle Folder Structure\n\n"
        puml += "[Repository Root] as Root\n"
        
        for f in self.files:
            rel = f['file'].replace('\\', '/')
            parts = Path(rel).parent.parts
            parent_id = "Root"
            current_folder = ""
            for idx, part in enumerate(parts):
                if not part or part == ".": continue
                current_folder = "/".join(parts[:idx+1])
                folder_id = f"Fold_{current_folder.replace('/', '_').replace('.', '_')}"
                if current_folder not in visited_folders:
                    mmd += f"    {parent_id} --> {folder_id}[\"Folder: {part}\"]\n"
                    puml += f"{parent_id} --> {folder_id}\n"
                    puml += f"node \"Folder: {part}\" as {folder_id}\n"
                    visited_folders.add(current_folder)
                parent_id = folder_id
                
            name = Path(rel).name
            file_id = f"File_{rel.replace('/', '_').replace('.', '_')}"
            mmd += f"    {parent_id} --> {file_id}[\"{name}\"]\n"
            puml += f"{parent_id} --> {file_id}\n"
            puml += f"file \"{name}\" as {file_id}\n"
            
        puml += "@endum\n"
        return mmd, puml

    def generate_service_flow(self) -> Tuple[str, str]:
        mmd = "flowchart TD\n"
        mmd += "    Start([Application Startup]) --> InitConfig[Load Config & Initialize Settings]\n"
        mmd += "    InitConfig --> ScanRepo[Scanner: Traverse Repository Files]\n"
        mmd += "    ScanRepo --> ParserEngine[Parser: Calculate LOC & Metrics]\n"
        mmd += "    ParserEngine --> ModulesAnalyze[Run Core Analysis Modules]\n"
        mmd += "    subgraph Core Modules [Analysis Modules]\n"
        mmd += "        Security[Module 02: Security Vulnerability Checker]\n"
        mmd += "        Metrics[Module 01: Code Metrics Analyzer]\n"
        mmd += "        Quality[Module 03: Code Analysis & Smells]\n"
        mmd += "        Contributor[Module 04: Contributor & Risk Analyzer]\n"
        mmd += "        RepoIntel[Module 05: Repository Intelligence]\n"
        mmd += "        Diagrams[Module 07: Diagrams Reporter]\n"
        mmd += "    end\n"
        mmd += "    ModulesAnalyze --> Security\n"
        mmd += "    ModulesAnalyze --> Metrics\n"
        mmd += "    ModulesAnalyze --> Quality\n"
        mmd += "    ModulesAnalyze --> Contributor\n"
        mmd += "    ModulesAnalyze --> RepoIntel\n"
        mmd += "    ModulesAnalyze --> Diagrams\n"
        mmd += "    Diagrams --> DrawDiag[Generate Architecture & Class Diagrams]\n"
        mmd += "    DrawDiag --> compileReport[Compile & Render Standalone HTML Report]\n"
        mmd += "    compileReport --> End([Save Output Files & Terminate])\n"
        
        puml = "@startuml\ntitle Service Flow Sequence\n\n"
        puml += "actor User\n"
        puml += "participant \"CLI / Entry\" as CLI\n"
        puml += "participant \"Repository Scanner\" as Scanner\n"
        puml += "participant \"Analysis Modules\" as Modules\n"
        puml += "participant \"Diagrams Module\" as Diags\n"
        puml += "participant \"HTML Report Generator\" as HTML\n\n"
        puml += "User -> CLI : Execute archon scan command\n"
        puml += "CLI -> CLI : Load config settings\n"
        puml += "CLI -> Scanner : Traverse directories and parse files\n"
        puml += "Scanner --> CLI : Return scan results payload\n"
        puml += "CLI -> Modules : Execute Metrics, Security, Code Analysis\n"
        puml += "Modules --> CLI : Save individual reports\n"
        puml += "CLI -> Diags : Execute Module 07 Diagrams Reporter\n"
        puml += "Diags -> Diags : Generate 14 architecture diagrams (Mermaid & PlantUML)\n"
        puml += "Diags -> HTML : Compile JSON files and render report.html\n"
        puml += "HTML --> User : Complete! Output reports directory\n"
        puml += "@endum\n"
        
        return mmd, puml

    def generate_call_graph(self) -> Tuple[str, str]:
        func_calls = []
        top_funcs = self.functions[:15]
        for f in top_funcs:
            name = f['name']
            file = f['file']
            
            for other_file in self.files:
                other_rel = other_file['file'].replace('\\', '/')
                if other_rel == file:
                    continue
                abs_path = self.root_path / other_rel
                try:
                    content = abs_path.read_text(encoding='utf-8', errors='ignore')
                    if re.search(r'\b' + name + r'\s*\(', content):
                        func_calls.append((other_rel, file, name))
                except Exception:
                    pass
                    
        mmd = "flowchart TD\n"
        puml = "@startuml\ntitle Function Call Graph\n\n"
        
        written_nodes = set()
        for other_rel, file, name in func_calls:
            caller_name = Path(other_rel).name
            callee_name = f"{Path(file).name}::{name}"
            
            caller_id = f"Func_{hash(other_rel)%10000}"
            callee_id = f"Func_{hash(file + name)%10000}"
            
            if caller_id not in written_nodes:
                mmd += f"    {caller_id}[\"{caller_name}\"]\n"
                puml += f"[{caller_name}] as {caller_id}\n"
                written_nodes.add(caller_id)
            if callee_id not in written_nodes:
                mmd += f"    {callee_id}[\"{callee_name}()\"]\n"
                puml += f"[{callee_name}()] as {callee_id}\n"
                written_nodes.add(callee_id)
                
            mmd += f"    {caller_id} --> {callee_id}\n"
            puml += f"{caller_id} --> {callee_id}\n"
            
        if not func_calls:
            mmd += "    Start([Main Scan]) --> RunReporter[Run Reports]\n"
            puml += "[Main Scan] --> [Run Reports]\n"
            
        puml += "@endum\n"
        return mmd, puml

    def generate_data_flow(self) -> Tuple[str, str]:
        mmd = "flowchart LR\n"
        mmd += "    subgraph Input [Inputs]\n"
        mmd += "        CLIArgs[CLI Arguments & Options]\n"
        mmd += "        Config[archon-config.json]\n"
        mmd += "        SrcFiles[Repository Source Files]\n"
        mmd += "    end\n\n"
        mmd += "    subgraph Process [Processing & AST Analyzer]\n"
        mmd += "        Scanner[Repository Scanner]\n"
        mmd += "        Parsers[Statically analyze classes, methods, imports]\n"
        mmd += "    end\n\n"
        mmd += "    subgraph Data Stores [Intermediary JSON Results]\n"
        mmd += "        MetricsJSON[02_file_metrics.json]\n"
        mmd += "        QualityJSON[02_complexity_analysis.json]\n"
        mmd += "        SecurityJSON[01_security_summary.json]\n"
        mmd += "    end\n\n"
        mmd += "    subgraph Output [Report Delivery]\n"
        mmd += "        ReportHTML[report.html (Interactive dashboard)]\n"
        mmd += "        TxtLogs[Text summary reports]\n"
        mmd += "    end\n\n"
        
        mmd += "    CLIArgs --> Scanner\n"
        mmd += "    Config --> Scanner\n"
        mmd += "    SrcFiles --> Scanner\n"
        mmd += "    Scanner --> Parsers\n"
        mmd += "    Parsers --> MetricsJSON\n"
        mmd += "    Parsers --> QualityJSON\n"
        mmd += "    Parsers --> SecurityJSON\n"
        mmd += "    MetricsJSON --> ReportHTML\n"
        mmd += "    QualityJSON --> ReportHTML\n"
        mmd += "    SecurityJSON --> ReportHTML\n"
        mmd += "    ReportHTML --> TxtLogs\n"
        
        puml = "@startuml\ntitle Data Flow Diagram\n\n"
        puml += "database \"Source Files\" as Src\n"
        puml += "node \"Scanner/AST\" as Scanner\n"
        puml += "database \"JSON Reports\" as JSON\n"
        puml += "node \"HTML Report Generator\" as HTML\n"
        puml += "file \"report.html\" as Report\n\n"
        puml += "Src --> Scanner : Reads contents\n"
        puml += "Scanner --> JSON : Writes findings\n"
        puml += "JSON --> HTML : Reads summary inputs\n"
        puml += "HTML --> Report : Saves interactive report\n"
        puml += "@endum\n"
        
        return mmd, puml

    def generate_class_relationships(self) -> Tuple[str, str]:
        mmd = "classDiagram\n"
        puml = "@startuml\ntitle Class Relationships\n\n"
        
        written_classes = set()
        inheritance_lines = []
        display_classes = self.classes[:20]
        
        for c in display_classes:
            name = c['name']
            parent = c['parent']
            file = c['file']
            
            if name not in written_classes:
                mmd += f"    class {name} {{\n"
                mmd += f"        +File: {Path(file).name}\n"
                mmd += "    }\n"
                puml += f"class {name} {{\n"
                puml += f"  File: {Path(file).name}\n"
                puml += "}\n"
                written_classes.add(name)
                
            if parent and parent != "None":
                p_clean = parent.split('.')[-1].split('(')[-1].strip()
                if p_clean not in written_classes:
                    mmd += f"    class {p_clean}\n"
                    puml += f"class {p_clean}\n"
                    written_classes.add(p_clean)
                inheritance_lines.append((p_clean, name))
                
        for parent, child in inheritance_lines:
            mmd += f"    {parent} <|-- {child}\n"
            puml += f"{parent} <|-- {child}\n"
            
        if not display_classes:
            mmd += "    class NoClassesDetected {\n"
            mmd += "        +Note: Codebase is function-based or configuration-oriented\n"
            mmd += "    }\n"
            puml += "class NoClassesDetected {\n"
            puml += "  Note: Codebase is function-based or configuration-oriented\n"
            puml += "}\n"
            
        puml += "@endum\n"
        return mmd, puml

    def generate_sequence_diagram(self) -> Tuple[str, str]:
        mmd = """sequenceDiagram
    autonumber
    User/CLI->>Scanner: scan(path)
    Scanner->>Parser: analyze_file(file)
    Parser-->>Scanner: metrics
    Scanner-->>User/CLI: scan_results
    User/CLI->>Reporters: generate_reports()
    Reporters->>Output: write files
    Reporters-->>User/CLI: report.html
"""
        puml = """@startuml
autonumber
"User/CLI" -> "Scanner" : scan(path)
"Scanner" -> "Parser" : analyze_file(file)
"Parser" --> "Scanner" : metrics
"Scanner" --> "User/CLI" : scan_results
"User/CLI" -> "Reporters" : generate_reports()
"Reporters" -> "Output" : write files
"Reporters" --> "User/CLI" : report.html
@endum
"""
        return mmd, puml

    def generate_state_diagram(self) -> Tuple[str, str]:
        mmd = """stateDiagram-v2
    [*] --> Uninitialized
    Uninitialized --> Configured : Load archon-config.json
    Configured --> Scanning : Scanner.scan()
    Scanning --> Analyzing : Modules.generate_reports()
    Analyzing --> Compiling : compile_and_write_html_report()
    Compiling --> Completed : Output HTML
    Completed --> [*]
"""
        puml = """@startuml
[*] --> Uninitialized
Uninitialized --> Configured : Load config
Configured --> Scanning : Scanner run
Scanning --> Analyzing : Run modules
Analyzing --> Compiling : HTML compile
Compiling --> Completed : Output reports
Completed --> [*]
@endum
"""
        return mmd, puml

    def generate_entity_relationship(self) -> Tuple[str, str]:
        mmd = """erDiagram
    REPOSITORY ||--|{ FILE : contains
    FILE ||--|{ CLASS : defines
    FILE ||--|{ FUNCTION : defines
    CLASS ||--|{ METHOD : contains
"""
        puml = """@startuml
entity "Repository" as Repo {
  * id : string
  --
  path : string
}
entity "File" as File {
  * path : string
  --
  language : string
  size_bytes : int
}
entity "Class" as Class {
  * name : string
  --
  parent : string
}
Repo ||--|{ File
File ||--|{ Class
@endum
"""
        return mmd, puml

    def generate_security_diagram(self) -> Tuple[str, str]:
        mmd = """flowchart TD
    subgraph Untrusted [Untrusted Boundary]
        Input[CLI / User Input]
        RemoteRepo[Remote Repository URL]
    end
    subgraph Trusted [Trusted Local Boundary]
        Scanner[Scanner & Sandbox Sanitizer]
        ASTParser[Lexical AST Parser]
        VulnChecker[Security Vulnerability Checker]
    end
    Input --> Scanner
    RemoteRepo --> Scanner
    Scanner --> ASTParser
    ASTParser --> VulnChecker
"""
        puml = """@startuml
node "Untrusted Boundary" {
  [User Input] as Input
  [Remote URL] as Remote
}
node "Trusted Boundary" {
  [Scanner] as Scanner
  [AST Parser] as Parser
  [Vulnerability Checker] as Security
}
Input --> Scanner
Remote --> Scanner
Scanner --> Parser
Parser --> Security
@endum
"""
        return mmd, puml

    def generate_reports(self):
        self.output_root.mkdir(parents=True, exist_ok=True)
        
        generators = {
            'architecture': self.generate_architecture,
            'component_diagram': self.generate_component_diagram,
            'module_diagram': self.generate_module_diagram,
            'package_diagram': self.generate_package_diagram,
            'dependency_diagram': self.generate_dependency_diagram,
            'folder_structure': self.generate_folder_structure,
            'service_flow': self.generate_service_flow,
            'call_graph': self.generate_call_graph,
            'data_flow': self.generate_data_flow,
            'class_relationships': self.generate_class_relationships,
            'sequence_diagram': self.generate_sequence_diagram,
            'state_diagram': self.generate_state_diagram,
            'entity_relationship': self.generate_entity_relationship,
            'security_diagram': self.generate_security_diagram
        }
        
        descriptions = {
            'architecture': 'High-level mapping of execution entry points, core subsystems, and specialized modular features.',
            'component_diagram': 'Architectural breakdown of Controller/CLI layers, Service business logic, Repository DB handlers, Utilities, and Configurations.',
            'module_diagram': 'Static inter-module dependencies and communication mapping across core and feature packages.',
            'package_diagram': 'Nested package and module filesystem hierarchy showing package dependencies.',
            'dependency_diagram': 'Complete internal import connections and external libraries dependency visualization. Highlights circular dependencies and shared helper modules.',
            'folder_structure': 'Visual directory folder tree mapping showing code layout and key modules grouping.',
            'service_flow': 'Sequential flow diagram mapping requests or scan execution pipeline from entry command down to report outputs.',
            'call_graph': 'Static call relationships and invocation hierarchy of major codebase functions.',
            'data_flow': 'Information movement flow showing inputs intake, static analysis processing, intermediate database/JSON storage, and report dashboard compilation.',
            'class_relationships': 'Class hierarchy diagram illustrating inheritance lines and class dependencies.',
            'sequence_diagram': 'Trace flow of execution from CLI run down to report output files.',
            'state_diagram': 'Diagram visualizing scanning lifecycle state transitions.',
            'entity_relationship': 'ER Diagram showing logical relationships between files, classes, methods, and functions.',
            'security_diagram': 'Trust boundaries and security scanning data flow mapping.'
        }
        
        titles = {
            'architecture': 'Overall Repository Architecture',
            'component_diagram': 'Component Diagram',
            'module_diagram': 'Module Diagram',
            'package_diagram': 'Package Diagram',
            'dependency_diagram': 'Dependency Diagram',
            'folder_structure': 'Folder Structure Diagram',
            'service_flow': 'Service Flow Diagram',
            'call_graph': 'Function Call Graph',
            'data_flow': 'Data Flow Diagram',
            'class_relationships': 'Class Relationship Diagram',
            'sequence_diagram': 'Sequence Diagram',
            'state_diagram': 'State Diagram',
            'entity_relationship': 'Entity Relationship Diagram',
            'security_diagram': 'Security Flow Diagram'
        }
        
        include_mmd = self.config.get("diagrams", {}).get("include_mmd", True)
        include_puml = self.config.get("diagrams", {}).get("include_puml", True)
        
        diagrams_payload = []
        for name, gen_fn in generators.items():
            try:
                mmd, puml = gen_fn()
                
                if include_mmd:
                    mmd_path = self.output_root / f"{name}.mmd"
                    mmd_path.write_text(mmd, encoding='utf-8')
                    
                if include_puml:
                    puml_path = self.output_root / f"{name}.puml"
                    puml_path.write_text(puml, encoding='utf-8')
                
                diagrams_payload.append({
                    'id': name,
                    'title': titles.get(name, name.replace('_', ' ').title()),
                    'description': descriptions.get(name, ''),
                    'mermaid': mmd,
                    'plantuml': puml
                })
            except Exception:
                pass
                
        json_path = self.output_root / "11_architecture_diagrams.json"
        json_data = {'diagrams': diagrams_payload}
        json_path.write_text(json.dumps(json_data, indent=2), encoding='utf-8')
        
        # Compile interactive HTML report for Module 07
        from archon.core.html_generator import compile_and_write_html_report
        nav = {"prev": "../05_Repository_Intelligence/report.html", "next": ""}
        compile_and_write_html_report(self.output_root, self.results, "Architecture Diagrams (Module 07)", nav)
