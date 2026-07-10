import unittest
from pathlib import Path
from archon.modules.contributor_analysis import ContributorAnalysisReporter

class TestContributorAnalysis(unittest.TestCase):
    def test_contributor_analysis_reporter(self):
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
        
        output_dir = Path.cwd() / "test_contributor_reports"
        reporter = ContributorAnalysisReporter(results, output_dir)
        reporter.generate_reports()
        
        # Verify that all 10 reports are created
        for filename in [
            "01_contributor_summary", "02_contributor_statistics", "03_commit_analysis",
            "04_file_ownership", "05_collaboration_analysis", "06_knowledge_distribution",
            "07_productivity_analysis", "08_repository_activity", "09_risk_analysis",
            "10_scan_metadata"
        ]:
            self.assertTrue((output_dir / f"{filename}.txt").exists(), f"{filename}.txt missing")
            self.assertTrue((output_dir / f"{filename}.json").exists(), f"{filename}.json missing")
            
        # Cleanup
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)

if __name__ == '__main__':
    unittest.main()
