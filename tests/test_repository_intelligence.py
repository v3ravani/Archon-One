import unittest
from pathlib import Path
from archon.modules.repository_intelligence import RepositoryIntelligenceReporter

class TestRepositoryIntelligence(unittest.TestCase):
    def test_repository_intelligence_reporter(self):
        results = {
            'root_path': str(Path.cwd()),
            'scan_duration': 0.5,
            'scan_id': 'test-scan-id',
            'files_scanned': [],
            'files_ignored': [],
            'counts': {
                'total_files': 0,
                'supported_files': 0,
                'ignored_files': 0,
                'binary_files': 0,
                'unsupported_files': 0,
                'hidden_files': 0,
                'total_directories': 1,
                'symlinks': 0,
                'executables': 0
            },
            'errors': [],
            'warnings': []
        }
        
        output_dir = Path.cwd() / "test_intelligence_reports"
        reporter = RepositoryIntelligenceReporter(results, output_dir)
        reporter.generate_reports()
        
        # Verify that all 10 reports are created
        for filename in [
            "01_repository_health", "02_hotspot_analysis", "03_technical_debt",
            "04_scalability_analysis", "05_testing_analysis", "06_refactoring_opportunities",
            "07_change_impact_analysis", "08_risk_prioritization", "09_repository_insights",
            "10_scan_metadata"
        ]:
            self.assertTrue((output_dir / f"{filename}.txt").exists(), f"{filename}.txt missing")
            self.assertTrue((output_dir / f"{filename}.json").exists(), f"{filename}.json missing")
            
        # Cleanup
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)

if __name__ == '__main__':
    unittest.main()
