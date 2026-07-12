import unittest
from pathlib import Path
from archon.modules.diagrams import DiagramsReporter

class TestDiagrams(unittest.TestCase):
    def test_diagrams_generation(self):
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
        
        config = {
            'diagrams': {
                'include_mmd': True,
                'include_puml': True,
                'max_nodes': 50
            }
        }
        
        output_dir = Path.cwd() / "test_diagram_reports"
        reporter = DiagramsReporter(results, output_dir, config)
        reporter.generate_reports()
        
        # Verify that all 14 diagrams are created
        diagram_types = [
            "architecture", "component_diagram", "module_diagram", "package_diagram",
            "dependency_diagram", "folder_structure", "service_flow", "call_graph",
            "data_flow", "class_relationships", "sequence_diagram", "state_diagram",
            "entity_relationship", "security_diagram"
        ]
        
        for name in diagram_types:
            self.assertTrue((output_dir / f"{name}.mmd").exists(), f"{name}.mmd missing")
            self.assertTrue((output_dir / f"{name}.puml").exists(), f"{name}.puml missing")
            
        self.assertTrue((output_dir / "11_architecture_diagrams.json").exists(), "11_architecture_diagrams.json missing")
        self.assertTrue((output_dir / "report.html").exists(), "report.html missing")
        
        # Cleanup
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)

if __name__ == '__main__':
    unittest.main()
