import sys
import time
import webbrowser
from pathlib import Path
from typing import Optional
import typer
from tabulate import tabulate

from archon.core.scanner import RepositoryScanner
from archon.modules.code_metrics import CodeMetricsReporter, format_size
from archon.modules.security import SecurityReporter
from archon.modules.code_analysis import CodeAnalysisReporter
from archon.modules.contributor_analysis import ContributorAnalysisReporter
from archon.modules.repository_intelligence import RepositoryIntelligenceReporter
from archon.modules.knowledge_graph import KnowledgeGraphReporter
from archon.modules.diagrams import DiagramsReporter


def execute_profile(profile_name: str, commands_list: list):
    typer.secho("================================================================================", fg=typer.colors.CYAN, bold=True)
    typer.secho(f"                  EXECUTING COMMAND PROFILE: {profile_name.upper()}", fg=typer.colors.CYAN, bold=True)
    typer.secho("================================================================================", fg=typer.colors.CYAN)
    typer.secho(f"[*] Executing sequence of {len(commands_list)} command(s)...", fg=typer.colors.CYAN)
    
    import shlex
    import subprocess
    
    for i, cmd_str in enumerate(commands_list):
        typer.secho(f"\n[>] [{i+1}/{len(commands_list)}] Running: {cmd_str}", fg=typer.colors.YELLOW, bold=True)
        cmd_clean = cmd_str.strip()
        if cmd_clean.lower().startswith("archon "):
            cmd_clean = cmd_clean[7:].strip()
        elif cmd_clean.lower().startswith("archon.exe "):
            cmd_clean = cmd_clean[11:].strip()
            
        tokens = shlex.split(cmd_clean)
        if not tokens:
            continue
            
        full_cmd = [sys.executable, "-m", "archon.cli"] + tokens
        res = subprocess.run(full_cmd)
        
        if res.returncode == 2 and tokens[0] not in {"scan", "graph", "diagrams", "report", "config", "git", "about", "help", "profiles"}:
            res = subprocess.run(shlex.split(cmd_str.strip()))

        if res.returncode != 0:
            typer.secho(f"[-] Command profile '{profile_name}' failed at step {i+1}: '{cmd_str}'", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=res.returncode)
            
    typer.secho(f"\n[+] Command profile '{profile_name}' completed successfully!", fg=typer.colors.GREEN, bold=True)
    typer.secho("================================================================================", fg=typer.colors.CYAN)

def prepare_target_directory(
    project_path: Optional[Path],
    source: Optional[Path],
    github: Optional[str]
) -> tuple:
    """
    Resolve target directory for scanning, graphing, or diagrams.
    Returns (target_path, temp_dir_to_clean_up)
    """
    if github:
        typer.secho(f"[*] Cloning GitHub repository: {github}...", fg=typer.colors.CYAN)
        import tempfile
        import subprocess
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir)
        try:
            subprocess.run(
                ["git", "clone", github, "."],
                cwd=temp_path,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            typer.secho("[+] Repository cloned successfully. Starting scan...", fg=typer.colors.GREEN)
            return temp_path, temp_dir
        except Exception as e:
            typer.secho(f"[-] Error cloning repository: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
            
    if source is not None:
        target_path = source.resolve()
    elif project_path is not None:
        target_path = project_path.resolve()
    else:
        target_path = Path.cwd().resolve()
        
    if not target_path.exists():
        typer.echo(f"Error: Path '{target_path}' does not exist.", err=True)
        raise typer.Exit(code=1)
        
    if not target_path.is_dir():
        typer.echo(f"Error: Path '{target_path}' is not a directory.", err=True)
        raise typer.Exit(code=1)
        
    return target_path, None

def show_guide():
    typer.secho("================================================================================", fg=typer.colors.CYAN, bold=True)
    typer.secho("                           ARCHON ONE RUNNING GUIDE                             ", fg=typer.colors.CYAN, bold=True)
    typer.secho("================================================================================", fg=typer.colors.CYAN)
    typer.echo()
    
    typer.secho("Core Scanning & Intelligence Commands:", fg=typer.colors.WHITE, bold=True)
    typer.echo()
    typer.secho("  1. archon scan                      - Scan codebase for metrics, security, & intelligence (excl. graph)", fg=typer.colors.YELLOW)
    typer.secho("     Options: -s/--source <path>      - Input source directory path", fg=typer.colors.CYAN)
    typer.secho("              -o/--output <path>      - Custom output directory path", fg=typer.colors.CYAN)
    typer.secho("              -g/--github <repo_url>  - Clone & scan remote GitHub repository", fg=typer.colors.CYAN)
    typer.echo()
    typer.secho("  2. archon graph                     - Generate 12-file Knowledge Graph schema & repository map", fg=typer.colors.YELLOW)
    typer.secho("     Options: -s/--source <path> | -o/--output <path> | -g/--github <repo_url>", fg=typer.colors.CYAN)
    typer.echo()
    typer.secho("  3. archon diagrams                  - Generate 14 architecture diagrams (Mermaid/SVG/PNG)", fg=typer.colors.YELLOW)
    typer.secho("     Options: -s/--source <path> | -o/--output <path> | -g/--github <repo_url>", fg=typer.colors.CYAN)
    typer.echo()
    typer.secho("Utility & Management Commands:", fg=typer.colors.WHITE, bold=True)
    typer.echo()
    typer.secho("  4. archon report [scan_dir]         - Compile scan results into unified index.html report", fg=typer.colors.YELLOW)
    typer.secho("  5. archon config                    - Launch offline Web Settings & Intelligence Dashboard", fg=typer.colors.YELLOW)
    typer.secho("  6. archon reset                     - Reset configuration to factory defaults", fg=typer.colors.YELLOW)
    typer.secho("  7. archon profiles                  - Manage Command Profiles (list, add, edit, delete)", fg=typer.colors.YELLOW)
    typer.secho("  8. archon vault                     - Secret Vault file protection (status, mask, unmask, change-password)", fg=typer.colors.YELLOW)
    typer.secho("  9. archon help                      - Show running guide instructions", fg=typer.colors.YELLOW)
    typer.secho(" 10. archon about                     - Show developer & version details", fg=typer.colors.YELLOW)
    typer.echo()
    
    # Load and show command profiles if present
    try:
        from archon.modules.settings_manager import load_config
        config_path = Path.cwd().resolve() / "archon-config.json"
        config = load_config(config_path)
        profiles = config.get("profiles", {})
        if profiles:
            typer.secho("Configured Command Profiles:", fg=typer.colors.WHITE, bold=True)
            typer.echo()
            idx = 11
            for p_name, p_cmds in profiles.items():
                cmd_count = len(p_cmds) if isinstance(p_cmds, list) else 0
                typer.secho(f"  {idx:2d}. archon {p_name:<25} - Execute profile '{p_name}' ({cmd_count} command(s))", fg=typer.colors.GREEN)
                idx += 1
            typer.echo()
    except Exception:
        pass

    typer.secho("================================================================================", fg=typer.colors.CYAN)

def help_callback(value: bool):
    if value:
        show_guide()
        raise typer.Exit()

def version_callback(value: bool):
    if value:
        import archon
        typer.echo(f"Archon One version: {archon.__version__}")
        raise typer.Exit()

app = typer.Typer(
    add_completion=False,
    context_settings={"help_option_names": []}
)

def register_command_profiles(app_instance: typer.Typer):
    try:
        from archon.modules.settings_manager import load_config, BUILTIN_COMMANDS
        config_path = Path.cwd().resolve() / "archon-config.json"
        config = load_config(config_path)
        profiles = config.get("profiles", {})
        
        for profile_name, commands_list in profiles.items():
            if not isinstance(commands_list, list) or not commands_list:
                continue
            if profile_name in BUILTIN_COMMANDS:
                continue
                
            def make_cmd(p_name, c_list):
                def profile_cmd():
                    execute_profile(p_name, c_list)
                profile_cmd.__doc__ = f"Execute command profile '{p_name}' ({len(c_list)} command(s))."
                return profile_cmd

            app_instance.command(name=profile_name)(make_cmd(profile_name, commands_list))
    except Exception:
        pass

register_command_profiles(app)

@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    help: Optional[bool] = typer.Option(
        None,
        "--help",
        help="Show guide instructions on how to run scans.",
        callback=help_callback,
        is_eager=True
    ),
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        "-v",
        help="Show Archon One version details.",
        callback=version_callback,
        is_eager=True
    )
):
    if ctx.invoked_subcommand is None:
        show_guide()
        raise typer.Exit()

@app.command()
def scan(
    project_path: Optional[Path] = typer.Argument(
        None, 
        help="Path to the project directory to scan (defaults to current directory)"
    ),
    source: Optional[Path] = typer.Option(
        None,
        "--source",
        "-s",
        help="Path to input source directory to scan"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Custom output directory to save reports"
    ),
    github: Optional[str] = typer.Option(
        None,
        "--github",
        "-g",
        help="Remote GitHub repository URL to clone and scan"
    )
):
    """
    Scan codebase for metrics, security, code analysis, contributor analysis, & intelligence (excluding Knowledge Graph).
    """
    target_path, temp_dir = prepare_target_directory(project_path, source, github)
    try:
        # Define progress callback
        def progress_callback(current: int, total: int, filepath: Path):
            percent = (current / total) * 100 if total > 0 else 0
            bar_length = 20
            filled_length = int(round(bar_length * current / float(total))) if total > 0 else 0
            bar = '=' * filled_length + '-' * (bar_length - filled_length)
            try:
                rel_path = str(filepath.relative_to(target_path))
            except Exception:
                rel_path = filepath.name
            if len(rel_path) > 35:
                rel_path = "..." + rel_path[-32:]
            sys.stdout.write(f"\r\033[96m[*]\033[0m Scan progress: [\033[92m{bar}\033[0m] \033[93m{percent:5.1f}%\033[0m ({current}/{total}) \033[90m{rel_path:<35}\033[0m")
            sys.stdout.flush()

        # Load configuration
        from archon.modules.settings_manager import load_config
        config = load_config(target_path / "archon-config.json")

        # 2. Run repository scanning
        scanner = RepositoryScanner(target_path)
        results = scanner.scan(progress_callback=progress_callback)
        sys.stdout.write("\n")
        sys.stdout.flush()
        counts = results['counts']
        
        # 3. Create timestamped report folder
        local_time = time.localtime(results.get('start_time', time.time()))
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", local_time)

        config_output = config.get('general', {}).get('output_folder', 'archon-one')
        if output is not None:
            output_base = Path(output).resolve()
        else:
            output_base = Path(config_output)
            if not output_base.is_absolute():
                output_base = target_path / output_base

        if config.get('general', {}).get('create_timestamp_folder', True):
            report_root = output_base / timestamp
        else:
            report_root = output_base
        
        # 4. Generate reports (EXCLUDING knowledge_graph)
        if config.get('modules', {}).get('code_metrics', True):
            typer.secho("[*] Generating metrics reports...", fg=typer.colors.CYAN)
            report_folder_metrics = report_root / "01_metrics"
            reporter_metrics = CodeMetricsReporter(results, report_folder_metrics)
            reporter_metrics.generate_reports()
        
        if config.get('modules', {}).get('security', True):
            typer.secho("[*] Generating security reports...", fg=typer.colors.CYAN)
            report_folder_security = report_root / "02_security"
            reporter_security = SecurityReporter(results, report_folder_security)
            reporter_security.generate_reports()
        
        if config.get('modules', {}).get('code_analysis', True):
            typer.secho("[*] Generating code analysis reports...", fg=typer.colors.CYAN)
            report_folder_analysis = report_root / "03_Code_Analysis"
            reporter_analysis = CodeAnalysisReporter(results, report_folder_analysis)
            reporter_analysis.generate_reports()
        
        if config.get('modules', {}).get('contributor_analysis', True):
            typer.secho("[*] Generating contributor analysis reports...", fg=typer.colors.CYAN)
            report_folder_contributor = report_root / "04_Contributor_Analysis"
            reporter_contributor = ContributorAnalysisReporter(results, report_folder_contributor)
            reporter_contributor.generate_reports()
        
        if config.get('modules', {}).get('repository_intelligence', True):
            typer.secho("[*] Generating repository intelligence reports...", fg=typer.colors.CYAN)
            report_folder_intelligence = report_root / "05_Repository_Intelligence"
            reporter_intelligence = RepositoryIntelligenceReporter(results, report_folder_intelligence)
            reporter_intelligence.generate_reports()

        if config.get('modules', {}).get('diagrams', True):
            typer.secho("[*] Generating architecture diagrams...", fg=typer.colors.CYAN)
            report_folder_diagrams = report_root / "07_Diagrams"
            reporter_diagrams = DiagramsReporter(results, report_folder_diagrams, config)
            reporter_diagrams.generate_reports()
        
        typer.secho("[*] Finalizing scan and saving reports...", fg=typer.colors.CYAN)
        
        # 5. Display scan summary
        duration = results['scan_duration']
        scanned_count = counts['supported_files']
        ignored_count = counts['ignored_files']
        total_files = counts['total_files']
        total_scanned_size = sum(f['size_bytes'] for f in results['files_scanned'])
        
        summary_data = [
            ["Total Files Found", total_files],
            ["Files Scanned", scanned_count],
            ["Files Ignored", ignored_count],
            ["Total Size Scanned", format_size(total_scanned_size)],
            ["Scan Duration", f"{duration:.3f} seconds"],
        ]
        
        typer.secho("\n" + "=" * 50, fg=typer.colors.YELLOW)
        typer.secho("               SCAN SUMMARY", fg=typer.colors.YELLOW, bold=True)
        typer.secho("=" * 50, fg=typer.colors.YELLOW)
        typer.echo(tabulate(summary_data, tablefmt="plain"))
        typer.secho("=" * 50, fg=typer.colors.YELLOW)
        # 5. Compile unified interactive HTML report & automatically open in browser
        try:
            from archon.core.unified_generator import generate_unified_html_report
            index_file = generate_unified_html_report(report_root)
            if index_file and index_file.exists():
                webbrowser.open(index_file.as_uri())
                typer.secho(f"[+] Interactive report compiled and opened in browser:\n   {index_file.as_uri()}", fg=typer.colors.CYAN, bold=True)
        except Exception:
            pass

        typer.secho(f"\n[+] Reports saved to:\n   {report_root}", fg=typer.colors.GREEN, bold=True)
        typer.secho("==================================================\n", fg=typer.colors.GREEN)
    finally:
        if temp_dir:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

@app.command(name="graph")
def graph_command(
    project_path: Optional[Path] = typer.Argument(
        None, 
        help="Path to repository to analyze (defaults to current directory)"
    ),
    source: Optional[Path] = typer.Option(
        None,
        "--source",
        "-s",
        help="Path to input source directory"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Custom output directory to save reports"
    ),
    github: Optional[str] = typer.Option(
        None,
        "--github",
        "-g",
        help="Remote GitHub repository URL to clone and scan"
    )
):
    """
    Generate a 12-file Knowledge Graph schema & repository map for the specified codebase.
    """
    target_path, temp_dir = prepare_target_directory(project_path, source, github)
    try:
        def progress_callback(current: int, total: int, filepath: Path):
            percent = (current / total) * 100 if total > 0 else 0
            bar_length = 20
            filled_length = int(round(bar_length * current / float(total))) if total > 0 else 0
            bar = '=' * filled_length + '-' * (bar_length - filled_length)
            try:
                rel_path = str(filepath.relative_to(target_path))
            except Exception:
                rel_path = filepath.name
            if len(rel_path) > 35:
                rel_path = "..." + rel_path[-32:]
            sys.stdout.write(f"\r\033[96m[*]\033[0m Scan progress: [\033[92m{bar}\033[0m] \033[93m{percent:5.1f}%\033[0m ({current}/{total}) \033[90m{rel_path:<35}\033[0m")
            sys.stdout.flush()

        from archon.modules.settings_manager import load_config
        config = load_config(target_path / "archon-config.json")

        scanner = RepositoryScanner(target_path)
        results = scanner.scan(progress_callback=progress_callback)
        sys.stdout.write("\n")
        sys.stdout.flush()
        
        local_time = time.localtime(results.get('start_time', time.time()))
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", local_time)

        config_output = config.get('general', {}).get('output_folder', 'archon-one')
        if output is not None:
            output_base = Path(output).resolve()
        else:
            output_base = Path(config_output)
            if not output_base.is_absolute():
                output_base = target_path / output_base

        if config.get('general', {}).get('create_timestamp_folder', True):
            report_root = output_base / timestamp
        else:
            report_root = output_base
        
        typer.secho("[*] Generating knowledge graph reports...", fg=typer.colors.CYAN)
        report_folder_graph = report_root / "knowledge-graph"
        reporter_graph = KnowledgeGraphReporter(results, report_folder_graph)
        reporter_graph.generate_reports()
        
        typer.secho(f"\n[+] Knowledge Graph saved to:\n   {report_folder_graph}", fg=typer.colors.GREEN, bold=True)
        typer.secho("==================================================\n", fg=typer.colors.GREEN)
    finally:
        if temp_dir:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

@app.command(name="diagrams")
def diagrams_command(
    project_path: Optional[Path] = typer.Argument(
        None, 
        help="Path to repository to analyze (defaults to current directory)"
    ),
    source: Optional[Path] = typer.Option(
        None,
        "--source",
        "-s",
        help="Path to input source directory"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Custom output directory to save reports"
    ),
    github: Optional[str] = typer.Option(
        None,
        "--github",
        "-g",
        help="Remote GitHub repository URL to clone and scan"
    )
):
    """
    Generate codebase architecture diagrams for the specified repository.
    """
    target_path, temp_dir = prepare_target_directory(project_path, source, github)
    try:
        def progress_callback(current: int, total: int, filepath: Path):
            percent = (current / total) * 100 if total > 0 else 0
            bar_length = 20
            filled_length = int(round(bar_length * current / float(total))) if total > 0 else 0
            bar = '=' * filled_length + '-' * (bar_length - filled_length)
            try:
                rel_path = str(filepath.relative_to(target_path))
            except Exception:
                rel_path = filepath.name
            if len(rel_path) > 35:
                rel_path = "..." + rel_path[-32:]
            sys.stdout.write(f"\r\033[96m[*]\033[0m Scan progress: [\033[92m{bar}\033[0m] \033[93m{percent:5.1f}%\033[0m ({current}/{total}) \033[90m{rel_path:<35}\033[0m")
            sys.stdout.flush()

        from archon.modules.settings_manager import load_config
        config = load_config(target_path / "archon-config.json")

        scanner = RepositoryScanner(target_path)
        results = scanner.scan(progress_callback=progress_callback)
        sys.stdout.write("\n")
        sys.stdout.flush()
        
        local_time = time.localtime(results.get('start_time', time.time()))
        timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", local_time)

        config_output = config.get('general', {}).get('output_folder', 'archon-one')
        if output is not None:
            output_base = Path(output).resolve()
        else:
            output_base = Path(config_output)
            if not output_base.is_absolute():
                output_base = target_path / output_base

        if config.get('general', {}).get('create_timestamp_folder', True):
            report_root = output_base / timestamp
        else:
            report_root = output_base
        
        typer.secho("[*] Generating architecture diagrams...", fg=typer.colors.CYAN)
        report_folder_diagrams = report_root / "07_Diagrams"
        reporter_diagrams = DiagramsReporter(results, report_folder_diagrams, config)
        reporter_diagrams.generate_reports()
        
        typer.secho(f"\n[+] Architecture Diagrams saved to:\n   {report_folder_diagrams}", fg=typer.colors.GREEN, bold=True)
        typer.secho("==================================================\n", fg=typer.colors.GREEN)
    finally:
        if temp_dir:
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)

@app.command(name="reset")
def reset_command():
    """Reset configuration to factory defaults."""
    from archon.modules.settings_manager import DEFAULT_CONFIG
    config_path = Path.cwd().resolve() / "archon-config.json"
    try:
        import json
        config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding='utf-8')
        typer.secho("[+] Configuration reset to factory defaults successfully.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Error resetting configuration: {e}", fg=typer.colors.RED, err=True)

@app.command(name="report")
def report_command(
    scan_dir: Optional[Path] = typer.Argument(
        None,
        help="Path to the scan results directory (e.g. archon-one/2026-07-10_00-24-14). Defaults to the latest directory inside output folder."
    )
):
    """
    Compile scan results inside a scan directory into a single unified interactive HTML report.
    """
    # Resolve scan_dir
    if scan_dir is None:
        from archon.modules.settings_manager import load_config
        config = load_config(Path.cwd().resolve() / "archon-config.json")
        config_output = config.get('general', {}).get('output_folder', 'archon-one')
        output_base = Path(config_output)
        if not output_base.is_absolute():
            output_base = Path.cwd().resolve() / output_base
            
        if not output_base.exists() or not output_base.is_dir():
            typer.secho(f"[-] No scans found at {output_base}. Please specify a scan folder path.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
            
        subdirs = [x for x in output_base.iterdir() if x.is_dir()]
        if not subdirs:
            typer.secho(f"[-] No scan directories found in {output_base}.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
        subdirs.sort(key=lambda x: x.name, reverse=True)
        scan_dir = subdirs[0]
    else:
        scan_dir = scan_dir.resolve()

    if not scan_dir.exists() or not scan_dir.is_dir():
        typer.secho(f"[-] Scan directory {scan_dir} does not exist.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    typer.secho(f"[*] Compiling single HTML report for scan folder: {scan_dir.name}", fg=typer.colors.CYAN)
    
    from archon.core.unified_generator import generate_unified_html_report
    try:
        index_file = generate_unified_html_report(scan_dir)
        if index_file and index_file.exists():
            webbrowser.open(index_file.as_uri())
            typer.secho(f"[+] Successfully compiled and opened unified HTML report in browser:\n   {index_file.as_uri()}", fg=typer.colors.GREEN, bold=True)
    except Exception as e:
        typer.secho(f"[-] Failed to compile unified report: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

config_app = typer.Typer(help="Manage configuration", invoke_without_command=True)
app.add_typer(config_app, name="config")

@config_app.callback(invoke_without_command=True)
def config_main(ctx: typer.Context, port: int = typer.Option(8085, help="Port to run the local server on")):
    if ctx.invoked_subcommand is None:
        from archon.modules.settings_manager import launch_settings_server
        launch_settings_server(Path.cwd().resolve(), port)

@config_app.command(name="reset")
def config_reset():
    """Reset configuration to factory defaults."""
    from archon.modules.settings_manager import DEFAULT_CONFIG
    config_path = Path.cwd().resolve() / "archon-config.json"
    try:
        import json
        config_path.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding='utf-8')
        typer.secho("[+] Configuration reset to factory defaults successfully.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Error resetting configuration: {e}", fg=typer.colors.RED, err=True)

profiles_app = typer.Typer(help="Manage Command Profiles", invoke_without_command=True)
app.add_typer(profiles_app, name="profiles")

def print_profiles_list():
    from archon.modules.settings_manager import load_config
    config_path = Path.cwd().resolve() / "archon-config.json"
    config = load_config(config_path)
    profiles = config.get("profiles", {})
    
    typer.secho("================================================================================", fg=typer.colors.CYAN, bold=True)
    typer.secho("                            SAVED COMMAND PROFILES                              ", fg=typer.colors.CYAN, bold=True)
    typer.secho("================================================================================", fg=typer.colors.CYAN)
    typer.echo()
    
    if not profiles:
        typer.secho("No command profiles saved yet.", fg=typer.colors.YELLOW)
        typer.secho("Create command profiles using 'archon profiles add <name> <cmds...>' or from 'archon config'.", fg=typer.colors.WHITE)
        typer.secho("================================================================================", fg=typer.colors.CYAN)
        return

    for p_name, p_cmds in profiles.items():
        cmd_list = p_cmds if isinstance(p_cmds, list) else []
        typer.secho(f"Profile: archon {p_name}", fg=typer.colors.GREEN, bold=True)
        typer.secho(f"  Executes ({len(cmd_list)} command(s)):", fg=typer.colors.WHITE)
        for idx, cmd in enumerate(cmd_list, 1):
            typer.secho(f"    {idx}. {cmd}", fg=typer.colors.YELLOW)
        typer.echo()

    typer.secho("================================================================================", fg=typer.colors.CYAN)
    typer.secho(f"Total Saved Profiles: {len(profiles)}", fg=typer.colors.CYAN, bold=True)
    typer.secho("================================================================================", fg=typer.colors.CYAN)

@profiles_app.callback(invoke_without_command=True)
def profiles_main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        print_profiles_list()

@profiles_app.command(name="list")
def profiles_list_command():
    """List all saved Command Profiles and their command sequences."""
    print_profiles_list()

@profiles_app.command(name="add")
def profiles_add_command(
    name: str = typer.Argument(..., help="Name of profile to create"),
    commands: list[str] = typer.Argument(..., help="Sequence of commands to execute")
):
    """Create a new Command Profile (e.g. archon profiles add backend 'archon scan' 'archon graph')."""
    from archon.modules.settings_manager import load_config, validate_profile_name, validate_profile_commands
    import json
    
    val_name, msg = validate_profile_name(name)
    if not val_name:
        typer.secho(f"[-] {msg}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)
        
    val_cmds, msg = validate_profile_commands(commands, profile_name=name)
    if not val_cmds:
        typer.secho(f"[-] {msg}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    config_path = Path.cwd().resolve() / "archon-config.json"
    config = load_config(config_path)
    if "profiles" not in config:
        config["profiles"] = {}
        
    config["profiles"][name] = commands
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    typer.secho(f"[+] Command profile '{name}' created successfully with {len(commands)} command(s).", fg=typer.colors.GREEN, bold=True)

@profiles_app.command(name="create")
def profiles_create_command(
    name: str = typer.Argument(..., help="Name of profile to create"),
    commands: list[str] = typer.Argument(..., help="Sequence of commands to execute")
):
    """Alias for archon profiles add."""
    profiles_add_command(name, commands)

@profiles_app.command(name="edit")
def profiles_edit_command(
    name: str = typer.Argument(..., help="Name of profile to edit"),
    commands: list[str] = typer.Argument(..., help="New sequence of commands to execute")
):
    """Edit an existing Command Profile."""
    from archon.modules.settings_manager import load_config, validate_profile_commands
    import json

    config_path = Path.cwd().resolve() / "archon-config.json"
    config = load_config(config_path)
    profiles = config.get("profiles", {})
    
    if name not in profiles:
        typer.secho(f"[-] Command profile '{name}' does not exist.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    val_cmds, msg = validate_profile_commands(commands, profile_name=name)
    if not val_cmds:
        typer.secho(f"[-] {msg}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    config["profiles"][name] = commands
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    typer.secho(f"[+] Command profile '{name}' updated successfully with {len(commands)} command(s).", fg=typer.colors.GREEN, bold=True)

@profiles_app.command(name="delete")
def profiles_delete_command(
    name: str = typer.Argument(..., help="Name of profile to delete")
):
    """Delete a Command Profile."""
    from archon.modules.settings_manager import load_config
    import json

    config_path = Path.cwd().resolve() / "archon-config.json"
    config = load_config(config_path)
    profiles = config.get("profiles", {})
    
    if name not in profiles:
        typer.secho(f"[-] Command profile '{name}' does not exist.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    del config["profiles"][name]
    config_path.write_text(json.dumps(config, indent=2), encoding='utf-8')
    typer.secho(f"[+] Command profile '{name}' deleted successfully.", fg=typer.colors.GREEN, bold=True)

@profiles_app.command(name="remove")
def profiles_remove_command(
    name: str = typer.Argument(..., help="Name of profile to remove")
):
    """Alias for archon profiles delete."""
    profiles_delete_command(name)

vault_app = typer.Typer(help="Manage Secret Vault file protection", invoke_without_command=True)
app.add_typer(vault_app, name="vault")

@vault_app.callback(invoke_without_command=True)
def vault_main(ctx: typer.Context):
    if ctx.invoked_subcommand is None:
        from archon.modules.vault import SecretVault
        vault = SecretVault(Path.cwd().resolve())
        status_info = vault.get_status()
        
        typer.secho("================================================================================", fg=typer.colors.CYAN, bold=True)
        typer.secho("                            SECRET VAULT STATUS                                ", fg=typer.colors.CYAN, bold=True)
        typer.secho("================================================================================", fg=typer.colors.CYAN)
        typer.echo()
        
        status_str = "Active (Initialized)" if status_info["initialized"] else "Not Initialized"
        color = typer.colors.GREEN if status_info["initialized"] else typer.colors.YELLOW
        typer.secho(f"Vault Status: {status_str}", fg=color, bold=True)
        typer.secho(f"Protected Files Count: {status_info['protected_count']}", fg=typer.colors.WHITE)
        typer.echo()

        if status_info["protected_files"]:
            table_data = []
            for f in status_info["protected_files"]:
                table_data.append([f["path"], f["masked_at"], f"{f['size_bytes']} bytes", "YES" if f["exists"] else "NO"])
            headers = ["File Path", "Masked At", "Original Size", "Exists"]
            typer.echo(tabulate(table_data, headers=headers, tablefmt="plain"))
            typer.echo()

        typer.secho("================================================================================", fg=typer.colors.CYAN)

@vault_app.command(name="mask")
def vault_mask_command(
    file_path: Path = typer.Argument(..., help="Path to sensitive file to encrypt and mask")
):
    """
    Encrypt and mask a sensitive file using AES-256-GCM.
    """
    from archon.modules.vault import SecretVault
    vault = SecretVault(Path.cwd().resolve())
    
    if not vault.is_initialized():
        typer.secho("[*] Secret Vault is not initialized yet.", fg=typer.colors.CYAN)
        password = typer.prompt("Set master password", hide_input=True)
        confirm = typer.prompt("Confirm master password", hide_input=True)
        if password != confirm:
            typer.secho("[-] Passwords do not match.", fg=typer.colors.RED, err=True)
            raise typer.Exit(code=1)
    else:
        password = typer.prompt("Enter master password", hide_input=True)

    try:
        rel_path = vault.mask_file(file_path, password)
        typer.secho(f"[+] File '{rel_path}' encrypted and protected in Secret Vault successfully.", fg=typer.colors.GREEN, bold=True)
    except Exception as e:
        typer.secho(f"[-] Masking failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@vault_app.command(name="unmask")
def vault_unmask_command(
    file_path: Path = typer.Argument(..., help="Path to encrypted file to unmask")
):
    """
    Decrypt and unmask a protected file using master password.
    """
    from archon.modules.vault import SecretVault
    vault = SecretVault(Path.cwd().resolve())
    
    if not vault.is_initialized():
        typer.secho("[-] Secret Vault is not initialized.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    password = typer.prompt("Enter master password", hide_input=True)
    try:
        rel_path = vault.unmask_file(file_path, password)
        typer.secho(f"[+] File '{rel_path}' decrypted and unmasked successfully.", fg=typer.colors.GREEN, bold=True)
    except Exception as e:
        typer.secho(f"[-] Unmasking failed: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@vault_app.command(name="status")
def vault_status_command():
    """
    Display Secret Vault protection status and list of protected files.
    """
    from archon.modules.vault import SecretVault
    vault = SecretVault(Path.cwd().resolve())
    status_info = vault.get_status()
    
    typer.secho("================================================================================", fg=typer.colors.CYAN, bold=True)
    typer.secho("                            SECRET VAULT STATUS                                ", fg=typer.colors.CYAN, bold=True)
    typer.secho("================================================================================", fg=typer.colors.CYAN)
    typer.echo()
    
    status_str = "Active (Initialized)" if status_info["initialized"] else "Not Initialized"
    color = typer.colors.GREEN if status_info["initialized"] else typer.colors.YELLOW
    typer.secho(f"Vault Status: {status_str}", fg=color, bold=True)
    typer.secho(f"Protected Files Count: {status_info['protected_count']}", fg=typer.colors.WHITE)
    typer.echo()

    if status_info["protected_files"]:
        table_data = []
        for f in status_info["protected_files"]:
            table_data.append([f["path"], f["masked_at"], f"{f['size_bytes']} bytes", "YES" if f["exists"] else "NO"])
        headers = ["File Path", "Masked At", "Original Size", "Exists"]
        typer.echo(tabulate(table_data, headers=headers, tablefmt="plain"))
        typer.echo()

    typer.secho("================================================================================", fg=typer.colors.CYAN)

@vault_app.command(name="change-password")
def vault_change_password_command():
    """
    Change Secret Vault master password and re-encrypt all protected files.
    """
    from archon.modules.vault import SecretVault
    vault = SecretVault(Path.cwd().resolve())
    
    if not vault.is_initialized():
        typer.secho("[-] Secret Vault is not initialized.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    old_pwd = typer.prompt("Enter current master password", hide_input=True)
    new_pwd = typer.prompt("Enter new master password", hide_input=True)
    confirm_pwd = typer.prompt("Confirm new master password", hide_input=True)
    if new_pwd != confirm_pwd:
        typer.secho("[-] Passwords do not match.", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    try:
        vault.change_password(old_pwd, new_pwd)
        typer.secho("[+] Master password updated and protected files re-encrypted successfully.", fg=typer.colors.GREEN, bold=True)
    except Exception as e:
        typer.secho(f"[-] Failed to change password: {e}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

@app.command(name="git")
def git_command(
    repo_url: str = typer.Argument(..., help="GitHub repository URL to clone and scan"),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Custom output directory to save reports"
    )
):
    """
    Clone a remote GitHub repository, run a full scan, and clean up the cloned repository.
    """
    import sys
    import tempfile
    import shutil
    import subprocess

    typer.secho(f"[*] Cloning repository: {repo_url}...", fg=typer.colors.CYAN)
    
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        temp_path = Path(temp_dir)
        
        try:
            try:
                # Run git clone
                subprocess.run(
                    ["git", "clone", repo_url, "."],
                    cwd=temp_path,
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
            except Exception as e:
                typer.secho(f"[-] Error cloning repository: {e}", fg=typer.colors.RED, err=True)
                raise typer.Exit(code=1)
                
            typer.secho("[+] Repository cloned successfully. Starting scan...", fg=typer.colors.GREEN)
            
            # Copy local config if exists
            local_config_file = Path.cwd().resolve() / "archon-config.json"
            if local_config_file.exists():
                shutil.copy(local_config_file, temp_path / "archon-config.json")
                
            # Load configuration
            from archon.modules.settings_manager import load_config
            config = load_config(temp_path / "archon-config.json")
            
            # Scanner Core execution
            scanner = RepositoryScanner(temp_path)
            
            # Define progress callback
            def progress_callback(current: int, total: int, filepath: Path):
                percent = (current / total) * 100 if total > 0 else 0
                bar_length = 20
                filled_length = int(round(bar_length * current / float(total))) if total > 0 else 0
                bar = '=' * filled_length + '-' * (bar_length - filled_length)
                try:
                    rel_path = str(filepath.relative_to(temp_path))
                except Exception:
                    rel_path = filepath.name
                if len(rel_path) > 35:
                    rel_path = "..." + rel_path[-32:]
                sys.stdout.write(f"\r\033[96m[*]\033[0m Scan progress: [\033[92m{bar}\033[0m] \033[93m{percent:5.1f}%\033[0m ({current}/{total}) \033[90m{rel_path:<35}\033[0m")
                sys.stdout.flush()

            results = scanner.scan(progress_callback=progress_callback)
            sys.stdout.write("\n")
            sys.stdout.flush()
            counts = results['counts']
            
            # Set target_path and project name based on repo url or name
            repo_name = repo_url.rstrip("/").split("/")[-1].replace(".git", "")
            results['root_path'] = str(temp_path)
            
            local_time = time.localtime(results.get('start_time', time.time()))
            timestamp = time.strftime("%Y-%m-%d_%H-%M-%S", local_time)

            config_output = config.get('general', {}).get('output_folder', 'archon-one')
            if output is not None:
                output_base = Path(output).resolve()
            else:
                output_base = Path.cwd().resolve() / config_output

            if config.get('general', {}).get('create_timestamp_folder', True):
                report_root = output_base / timestamp
            else:
                report_root = output_base

            # Run reports
            if config.get('modules', {}).get('code_metrics', True):
                typer.secho("[*] Generating metrics reports...", fg=typer.colors.CYAN)
                report_folder_metrics = report_root / "01_metrics"
                reporter_metrics = CodeMetricsReporter(results, report_folder_metrics)
                reporter_metrics.generate_reports()

            if config.get('modules', {}).get('security', True):
                typer.secho("[*] Generating security reports...", fg=typer.colors.CYAN)
                report_folder_security = report_root / "02_security"
                reporter_security = SecurityReporter(results, report_folder_security)
                reporter_security.generate_reports()

            if config.get('modules', {}).get('code_analysis', True):
                typer.secho("[*] Generating code analysis reports...", fg=typer.colors.CYAN)
                report_folder_analysis = report_root / "03_Code_Analysis"
                reporter_analysis = CodeAnalysisReporter(results, report_folder_analysis)
                reporter_analysis.generate_reports()

            if config.get('modules', {}).get('contributor_analysis', True):
                typer.secho("[*] Generating contributor analysis reports...", fg=typer.colors.CYAN)
                report_folder_contributor = report_root / "04_Contributor_Analysis"
                reporter_contributor = ContributorAnalysisReporter(results, report_folder_contributor)
                reporter_contributor.generate_reports()

            if config.get('modules', {}).get('repository_intelligence', True):
                typer.secho("[*] Generating repository intelligence reports...", fg=typer.colors.CYAN)
                report_folder_intelligence = report_root / "05_Repository_Intelligence"
                reporter_intelligence = RepositoryIntelligenceReporter(results, report_folder_intelligence)
                reporter_intelligence.generate_reports()

            if config.get('modules', {}).get('knowledge_graph', True):
                typer.secho("[*] Generating knowledge graph reports...", fg=typer.colors.CYAN)
                report_folder_graph = report_root / "06_knowledge_graph"
                reporter_graph = KnowledgeGraphReporter(results, report_folder_graph)
                reporter_graph.generate_reports()

            if config.get('modules', {}).get('diagrams', True):
                typer.secho("[*] Generating architecture diagrams...", fg=typer.colors.CYAN)
                report_folder_diagrams = report_root / "07_Diagrams"
                reporter_diagrams = DiagramsReporter(results, report_folder_diagrams, config)
                reporter_diagrams.generate_reports()

            typer.secho("[*] Finalizing scan and saving reports...", fg=typer.colors.CYAN)

            duration = results['scan_duration']
            scanned_count = counts['supported_files']
            ignored_count = counts['ignored_files']
            total_files = counts['total_files']
            total_scanned_size = sum(f['size_bytes'] for f in results['files_scanned'])

            summary_data = [
                ["Repository Name", repo_name],
                ["Total Files Found", total_files],
                ["Files Scanned", scanned_count],
                ["Files Ignored", ignored_count],
                ["Total Size Scanned", format_size(total_scanned_size)],
                ["Scan Duration", f"{duration:.3f} seconds"],
            ]

            typer.secho("\n" + "=" * 50, fg=typer.colors.YELLOW)
            typer.secho("               SCAN SUMMARY", fg=typer.colors.YELLOW, bold=True)
            typer.secho("=" * 50, fg=typer.colors.YELLOW)
            typer.echo(tabulate(summary_data, tablefmt="plain"))
            typer.secho("=" * 50, fg=typer.colors.YELLOW)
            typer.secho(f"\n[+] Reports saved to:\n   {report_root}", fg=typer.colors.GREEN, bold=True)
            typer.secho("==================================================\n", fg=typer.colors.GREEN)
        finally:
            import stat
            import os
            def make_writable_and_remove(func, p, exc_info):
                try:
                    os.chmod(p, stat.S_IWRITE)
                    func(p)
                except Exception:
                    pass
            try:
                if temp_path.exists():
                    import sys
                    if sys.version_info >= (3, 12):
                        shutil.rmtree(temp_path, onexc=make_writable_and_remove)
                    else:
                        shutil.rmtree(temp_path, onerror=make_writable_and_remove)
            except Exception:
                pass

@app.command(name="about")
def about_command():
    """
    Show information about Archon One.
    """
    typer.secho("================================================================================", fg=typer.colors.CYAN, bold=True)
    typer.secho("                           ABOUT ARCHON ONE                                     ", fg=typer.colors.CYAN, bold=True)
    typer.secho("================================================================================", fg=typer.colors.CYAN)
    typer.echo()
    typer.secho("Developer: Viraj Ravani", fg=typer.colors.YELLOW, bold=True)
    typer.secho("Version:   0.2.0", fg=typer.colors.WHITE)
    typer.secho("License:   MIT", fg=typer.colors.WHITE)
    typer.secho("================================================================================", fg=typer.colors.CYAN)

@app.command(name="help")
def help_command():
    """
    Show guide instructions on how to run scans.
    """
    show_guide()


if __name__ == "__main__":
    app()
