import unittest
from pathlib import Path
import shutil
import json
from archon.modules.knowledge_graph import KnowledgeGraphReporter

class TestKnowledgeGraph(unittest.TestCase):
    def test_graph_node_and_edge_generation(self):
        # Mock results dictionary
        results = {
            'root_path': str(Path.cwd()),
            'scan_duration': 0.1,
            'scan_id': 'test-graph-scan-id',
            'files_scanned': [
                {
                    'file': 'src/archon/cli.py',
                    'name': 'cli.py',
                    'language': 'Python',
                    'lang_id': 'python',
                    'extension': '.py',
                    'size_bytes': 1000,
                    'physical_loc': 150,
                    'logical_loc': 100,
                    'blank_lines': 20,
                    'comment_lines': 30,
                    'comment_density': 30.0
                }
            ],
            'files_ignored': [],
            'counts': {
                'total_files': 1,
                'supported_files': 1,
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

        output_dir = Path.cwd() / "test_graph_reports"
        shutil.rmtree(output_dir, ignore_errors=True)

        reporter = KnowledgeGraphReporter(results, output_dir)
        reporter.generate_reports()

        # Check deliverables exist
        expected_files = [
            "metadata.json", "nodes.json", "edges.json", "files.json", "folders.json",
            "classes.json", "functions.json", "dependencies.json", "call-graph.json",
            "api-endpoints.json", "metrics.json", "diagnostics.json",
            "graph_summary.txt", "repository_map.md"
        ]

        for fname in expected_files:
            file_path = output_dir / fname
            self.assertTrue(file_path.exists(), f"{fname} is missing")

        # Load nodes.json and verify structure
        nodes = json.loads((output_dir / "nodes.json").read_text(encoding='utf-8'))
        self.assertTrue(any(n['type'] == 'Repository' for n in nodes))
        self.assertTrue(any(n['type'] == 'File' for n in nodes))

        # Cleanup
        shutil.rmtree(output_dir, ignore_errors=True)

if __name__ == '__main__':
    unittest.main()
