import unittest
from pathlib import Path
from archon.modules.code_analysis import clean_file_content, CodeAnalysisReporter

class TestCodeAnalysis(unittest.TestCase):
    def test_clean_file_content_python(self):
        code = """def hello():
    # This is a comment
    print("Hello, world!")  # Inline comment
"""
        cleaned, comments, strings = clean_file_content(code, 'python')
        # Check that comment text is replaced by spaces
        self.assertNotIn('#', cleaned)
        # Check that string content is replaced by spaces
        self.assertIn('"             "', cleaned)
        self.assertEqual(len(comments), 2)
        self.assertEqual(len(strings), 1)

    def test_clean_file_content_java(self):
        code = """public class Main {
    /* Block comment
       across lines */
    public static void main(String[] args) {
        // Line comment
        System.out.println("Hello");
    }
}"""
        cleaned, comments, strings = clean_file_content(code, 'java')
        self.assertNotIn("Block comment", cleaned)
        self.assertNotIn("Line comment", cleaned)
        self.assertIn('"     "', cleaned)
        self.assertEqual(len(comments), 2)
        self.assertEqual(len(strings), 1)

    def test_complexity_and_class_parsing(self):
        from archon.modules.code_analysis import clean_file_content
        # Python sample class
        code = """class MyClass(Parent):
    def __init__(self, value):
        self.value = value
    def run_process(self, cb):
        if self.value > 10:
            for i in range(5):
                cb(i)
        return
"""
        cleaned, comments, strings = clean_file_content(code, 'python')
        lines = cleaned.splitlines()
        
        # Test complexity analyzer
        reporter = CodeAnalysisReporter({'root_path': '.', 'files_scanned': [], 'files_ignored': [], 'counts': {}, 'errors': [], 'warnings': [], 'scan_duration': 0.0}, Path.cwd())
        comp = reporter._analyze_complexity(cleaned, lines, 'python')
        self.assertEqual(comp['cyclomatic'], 3)  # base (1) + if (1) + for (1)
        self.assertEqual(comp['decision_count'], 1)
        self.assertEqual(comp['loop_count'], 1)
        
        # Test function and class analyzer
        funcs, classes = reporter._analyze_functions_and_classes(cleaned, lines, 'test.py', 'python', comments)
        self.assertEqual(len(classes), 1)
        self.assertEqual(classes[0]['name'], 'MyClass')
        self.assertEqual(classes[0]['parent'], 'Parent')
        
        self.assertEqual(len(funcs), 2)
        self.assertEqual(funcs[0]['name'], '__init__')
        self.assertEqual(funcs[1]['name'], 'run_process')
        self.assertEqual(funcs[1]['parameters'], 2)  # self, cb
        self.assertEqual(funcs[1]['loops'], 1)
        self.assertEqual(funcs[1]['branches'], 1)
        self.assertEqual(funcs[1]['callbacks'], 1)  # 'cb' parameter

    def test_code_analysis_reporter(self):
        # Mock results dictionary
        results = {
            'root_path': str(Path.cwd()),
            'scan_duration': 0.5,
            'scan_id': 'test-scan-id',
            'files_scanned': [
                {
                    'file': 'src/archon/cli.py',
                    'language': 'Python',
                    'lang_id': 'python',
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
        
        output_dir = Path.cwd() / "test_reports"
        reporter = CodeAnalysisReporter(results, output_dir)
        reporter.generate_reports()
        
        # Verify that report files are created
        for filename in [
            "01_quality_summary", "02_complexity_analysis", "03_function_analysis",
            "04_class_analysis", "05_dependency_analysis", "06_duplication_analysis",
            "07_architecture_analysis", "08_code_smells", "09_maintainability",
            "10_scan_metadata"
        ]:
            self.assertTrue((output_dir / f"{filename}.txt").exists(), f"{filename}.txt missing")
            self.assertTrue((output_dir / f"{filename}.json").exists(), f"{filename}.json missing")
            
        # Cleanup
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)

    def test_comparison_since_last_scan(self):
        reporter = CodeAnalysisReporter({'root_path': '.', 'files_scanned': [], 'files_ignored': [], 'counts': {}, 'errors': [], 'warnings': [], 'scan_duration': 0.0}, Path.cwd())
        # Mock previous quality summary structure
        reporter.prev_quality = {
            'overall_quality_score': 85.0,
            'maintainability_grade': 'B',
            'technical_debt_score': 10.0,
            'averages': {
                'complexity': 2.0,
                'function_length': 10.0,
                'class_size': 50.0,
                'file_size': 100.0
            },
            'findings_summary': {'total': 5}
        }
        diff_pos = reporter._get_diff_text(90.0, 85.0)
        self.assertEqual(diff_pos, " (+5.00)")
        diff_neg = reporter._get_diff_text(3, 5)
        self.assertEqual(diff_neg, " (-2)")

if __name__ == '__main__':
    unittest.main()
