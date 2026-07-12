import sys
import time
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


def show_guide():
    typer.secho("================================================================================", fg=typer.colors.CYAN, bold=True)
    typer.secho("                           ARCHON ONE RUNNING GUIDE                             ", fg=typer.colors.CYAN, bold=True)
    typer.secho("================================================================================", fg=typer.colors.CYAN)
    typer.echo()
    
    typer.secho("Available commands:", fg=typer.colors.WHITE, bold=True)
    typer.echo()
    typer.secho("  1. archon scan                     - Scan the current repository", fg=typer.colors.YELLOW)
    typer.secho("  2. archon scan <path>              - Scan a repository at a custom path", fg=typer.colors.YELLOW)
    typer.secho("  3. archon scan -o <out_path>       - Scan and save report files to a custom path", fg=typer.colors.YELLOW)
    typer.secho("  4. archon graph                    - Generate a Knowledge Graph for the current directory", fg=typer.colors.YELLOW)
    typer.secho("  5. archon graph <path>             - Generate a Knowledge Graph for the specified repository", fg=typer.colors.YELLOW)
    typer.secho("  6. archon git <repo_url>           - Clone a remote GitHub repo and scan it", fg=typer.colors.YELLOW)
    typer.secho("  7. archon diagrams                 - Generate 14 architecture diagrams for the current repository", fg=typer.colors.YELLOW)
    typer.secho("  8. archon diagrams <path>          - Generate 14 architecture diagrams for repository at a custom path", fg=typer.colors.YELLOW)
    typer.secho("  9. archon report                   - Compile latest scan results into a single index.html", fg=typer.colors.YELLOW)
    typer.secho(" 10. archon report <scan_path>       - Compile scan results at custom path to a single index.html", fg=typer.colors.YELLOW)
    typer.secho(" 11. archon config                   - Launch the offline settings dashboard page", fg=typer.colors.YELLOW)
    typer.secho(" 12. archon config reset             - Reset all settings back to defaults", fg=typer.colors.YELLOW)
    typer.secho(" 13. archon help                     - Show running guide instructions", fg=typer.colors.YELLOW)
    typer.secho(" 14. archon about                    - Show developer and about details", fg=typer.colors.YELLOW)
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
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Custom output directory to save reports"
    )
):
    """
    Scan a project folder for metrics and security.
    
    Examples:
      archon scan
      archon scan C:\\Users\\ravan\\Desktop\\asthabyte
      archon scan -o C:\\Users\\ravan\\Desktop\\custom_output
    """
    # 1. Validate project directory
    if project_path is None:
        target_path = Path.cwd().resolve()
    else:
        target_path = project_path.resolve()
        
    if not target_path.exists():
        typer.echo(f"Error: Path '{target_path}' does not exist.", err=True)
        raise typer.Exit(code=1)
        
    if not target_path.is_dir():
        typer.echo(f"Error: Path '{target_path}' is not a directory.", err=True)
        raise typer.Exit(code=1)
        
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
    
    # 3. Create the timestamped report folder
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
    
    # 4. Generate reports
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
    
    # 5. Display scan summary
    duration = results['scan_duration']
    scanned_count = counts['supported_files']
    ignored_count = counts['ignored_files']
    total_files = counts['total_files']
    
    # Calculate scanned sizes
    total_scanned_size = sum(f['size_bytes'] for f in results['files_scanned'])
    
    # Summary console tables
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
    # Show output save path
    typer.secho(f"\n[+] Reports saved to:\n   {report_root}", fg=typer.colors.GREEN, bold=True)
    typer.secho("==================================================\n", fg=typer.colors.GREEN)

@app.command(name="graph")
def graph_command(
    project_path: Optional[Path] = typer.Argument(
        None, 
        help="Path to repository to analyze (defaults to current directory)"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Custom output directory to save reports"
    )
):
    """
    Generate a Knowledge Graph for the specified repository (or current directory).
    """
    # 1. Validate project directory
    if project_path is None:
        target_path = Path.cwd().resolve()
    else:
        target_path = project_path.resolve()
        
    if not target_path.exists():
        typer.echo(f"Error: Path '{target_path}' does not exist.", err=True)
        raise typer.Exit(code=1)
        
    if not target_path.is_dir():
        typer.echo(f"Error: Path '{target_path}' is not a directory.", err=True)
        raise typer.Exit(code=1)
        
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
    
    # 3. Create the timestamped report folder
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
    report_folder_graph = report_root / "06_knowledge_graph"
    reporter_graph = KnowledgeGraphReporter(results, report_folder_graph)
    reporter_graph.generate_reports()
    
    typer.secho(f"\n[+] Knowledge Graph saved to:\n   {report_folder_graph}", fg=typer.colors.GREEN, bold=True)
    typer.secho("==================================================\n", fg=typer.colors.GREEN)

@app.command(name="diagrams")
def diagrams_command(
    project_path: Optional[Path] = typer.Argument(
        None, 
        help="Path to repository to analyze (defaults to current directory)"
    ),
    output: Optional[Path] = typer.Option(
        None,
        "--output",
        "-o",
        help="Custom output directory to save reports"
    )
):
    """
    Generate codebase architecture diagrams for the specified repository (or current directory).
    """
    # 1. Validate project directory
    if project_path is None:
        target_path = Path.cwd().resolve()
    else:
        target_path = project_path.resolve()
        
    if not target_path.exists():
        typer.echo(f"Error: Path '{target_path}' does not exist.", err=True)
        raise typer.Exit(code=1)
        
    if not target_path.is_dir():
        typer.echo(f"Error: Path '{target_path}' is not a directory.", err=True)
        raise typer.Exit(code=1)
        
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
    
    # 3. Create the timestamped report folder
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
        typer.secho(f"[+] Successfully compiled single HTML report at:\n   {index_file}", fg=typer.colors.GREEN, bold=True)
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
