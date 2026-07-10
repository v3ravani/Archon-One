import unittest
import json
import shutil
from pathlib import Path
from archon.modules.settings_manager import load_config, DEFAULT_CONFIG
from archon.core.scanner import RepositoryScanner
from archon.modules.code_metrics import CodeMetricsReporter

class TestSettingsManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path.cwd() / "test_settings_workspace"
        self.test_dir.mkdir(exist_ok=True)
        self.config_path = self.test_dir / "archon-config.json"

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_config_creation(self):
        # File shouldn't exist initially
        self.assertFalse(self.config_path.exists())
        
        cfg = load_config(self.config_path)
        self.assertTrue(self.config_path.exists())
        self.assertEqual(cfg["general"]["project_name"], "Archon One Project")

    def test_scanner_custom_ignores(self):
        # Create mock file structure
        (self.test_dir / "src").mkdir(exist_ok=True)
        (self.test_dir / "ignored_dir").mkdir(exist_ok=True)
        
        (self.test_dir / "src" / "main.py").write_text("print('Hello')", encoding='utf-8')
        (self.test_dir / "src" / "test.log").write_text("log data", encoding='utf-8')
        (self.test_dir / "ignored_dir" / "other.py").write_text("print('Ignore me')", encoding='utf-8')
        
        # Write config specifying custom ignored folders, ignore files patterns, extensions
        custom_cfg = dict(DEFAULT_CONFIG)
        custom_cfg['ignore_rules'] = {
            "ignore_directories": ["ignored_dir"],
            "ignore_files": ["*.log"],
            "ignore_extensions": ["txt"],
            "ignore_hidden_files": True,
            "ignore_hidden_directories": True,
            "ignore_binary_files": True,
            "max_file_size": 10000
        }
        
        self.config_path.write_text(json.dumps(custom_cfg, indent=2), encoding='utf-8')
        
        # Instantiate scanner
        scanner = RepositoryScanner(self.test_dir)
        results = scanner.scan()
        
        # Extract scanned file paths
        scanned_files = [f['file'] for f in results['files_scanned']]
        
        self.assertIn("src\\main.py", scanned_files)
        self.assertNotIn("src\\test.log", scanned_files)
        self.assertNotIn("ignored_dir\\other.py", scanned_files)

    def test_reporter_output_configuration(self):
        # Disable json output, only enable txt output
        custom_cfg = dict(DEFAULT_CONFIG)
        custom_cfg['output'] = {
            "txt": True,
            "json": False,
            "output_tables": "ASCII",
            "sort_reports_by": "Severity",
            "max_rows_per_report": 100,
            "show_empty_reports": False,
            "compress_reports": False,
            "overwrite_existing_reports": True
        }
        self.config_path.write_text(json.dumps(custom_cfg, indent=2), encoding='utf-8')
        
        # Create a mock code file to yield real scanned metrics
        (self.test_dir / "src").mkdir(exist_ok=True)
        (self.test_dir / "src" / "main.py").write_text("print('Hello')", encoding='utf-8')
        
        scanner = RepositoryScanner(self.test_dir)
        results = scanner.scan()
        
        output_dir = self.test_dir / "reports"
        reporter = CodeMetricsReporter(results, output_dir)
        reporter.generate_reports()
        
        # TXT report should exist, JSON report should NOT exist
        self.assertTrue((output_dir / "01_repository_summary.txt").exists())
        self.assertFalse((output_dir / "01_repository_summary.json").exists())

    def test_reporter_md_output_configuration(self):
        # Enable md and txt output, disable json output
        custom_cfg = dict(DEFAULT_CONFIG)
        custom_cfg['output'] = {
            "txt": True,
            "json": False,
            "md": True,
            "output_tables": "ASCII",
            "sort_reports_by": "Severity",
            "max_rows_per_report": 100,
            "show_empty_reports": False,
            "compress_reports": False,
            "overwrite_existing_reports": True
        }
        self.config_path.write_text(json.dumps(custom_cfg, indent=2), encoding='utf-8')
        
        # Create a mock code file to yield real scanned metrics
        (self.test_dir / "src").mkdir(exist_ok=True)
        (self.test_dir / "src" / "main.py").write_text("print('Hello')", encoding='utf-8')
        
        scanner = RepositoryScanner(self.test_dir)
        results = scanner.scan()
        
        output_dir = self.test_dir / "reports"
        reporter = CodeMetricsReporter(results, output_dir)
        reporter.generate_reports()
        
        # TXT, MD, and HTML reports should exist, JSON report should NOT exist
        self.assertTrue((output_dir / "01_repository_summary.txt").exists())
        self.assertTrue((output_dir / "01_repository_summary.md").exists())
        self.assertFalse((output_dir / "01_repository_summary.json").exists())
        self.assertTrue((output_dir / "report.html").exists())

    def test_cli_about_command(self):
        from typer.testing import CliRunner
        from archon.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["about"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Viraj Ravani", result.output)

    def test_cli_help_command(self):
        from typer.testing import CliRunner
        from archon.cli import app
        runner = CliRunner()
        result = runner.invoke(app, ["help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("ARCHON ONE RUNNING GUIDE", result.output)

    def test_cli_scan_custom_output(self):
        from typer.testing import CliRunner
        from archon.cli import app
        runner = CliRunner()
        
        # Create a mock workspace to scan
        (self.test_dir / "src").mkdir(exist_ok=True)
        (self.test_dir / "src" / "main.py").write_text("print('Hello')", encoding='utf-8')
        
        custom_out = self.test_dir / "custom_out_dir"
        result = runner.invoke(app, ["scan", str(self.test_dir), "-o", str(custom_out)])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue(custom_out.exists())
        
        # Check that reports were generated under custom_out folder (under timestamp folder)
        timestamp_folders = [x for x in custom_out.iterdir() if x.is_dir()]
        self.assertTrue(len(timestamp_folders) > 0)
        scan_folder = timestamp_folders[0]
        self.assertTrue((scan_folder / "01_metrics" / "report.html").exists())

    def test_cli_report_generation(self):
        from typer.testing import CliRunner
        from archon.cli import app
        runner = CliRunner()
        
        # Setup mock scan directory with metrics json files
        mock_scan_dir = self.test_dir / "mock_scan_timestamp"
        metrics_dir = mock_scan_dir / "01_metrics"
        metrics_dir.mkdir(parents=True, exist_ok=True)
        
        # Write dummy metrics summary json
        dummy_summary = {
            "repository_overview": {
                "total_files": 5,
                "supported_files": 3
            }
        }
        (metrics_dir / "01_repository_summary.json").write_text(json.dumps(dummy_summary), encoding='utf-8')
        
        # Run report compilation
        result = runner.invoke(app, ["report", str(mock_scan_dir)])
        self.assertEqual(result.exit_code, 0)
        self.assertTrue((mock_scan_dir / "index.html").exists())

if __name__ == '__main__':
    unittest.main()
