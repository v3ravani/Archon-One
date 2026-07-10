import os
import re
import json
import time
import getpass
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from tabulate import tabulate

from archon.core.scanner import get_extension_category
from archon.modules.code_metrics import format_size

SEVERITY_ORDER = {
    "Critical": 0,
    "High": 1,
    "Medium": 2,
    "Low": 3,
    "Informational": 4
}

class Finding:
    def __init__(self, file: str, line: int, severity: str, category: str, issue_type: str, matched_pattern: str, masked_value: str, recommendation: str, line_content: str):
        self.file = file
        self.line = line
        self.severity = severity  # Critical, High, Medium, Low, Informational
        self.category = category  # Secrets, Credentials, Insecure Functions, Web Security, Cryptography, Dependency, Configuration, Sensitive Files, General
        self.issue_type = issue_type
        self.matched_pattern = matched_pattern
        self.masked_value = masked_value
        self.recommendation = recommendation
        self.line_content = line_content

    def get_signature(self) -> str:
        """Unique signature of the finding, insensitive to line number shifts."""
        return f"{self.file}:{self.category}:{self.issue_type}:{self.matched_pattern}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "file": self.file,
            "line": self.line,
            "severity": self.severity,
            "category": self.category,
            "issue_type": self.issue_type,
            "matched_pattern": self.matched_pattern,
            "masked_value": self.masked_value,
            "recommendation": self.recommendation,
            "line_content": self.line_content
        }


class SecurityReporter:
    def __init__(self, results: Dict[str, Any], output_root: Path):
        self.results = results
        self.output_root = output_root
        self.root_path = Path(results['root_path'])
        self.scanned = results['files_scanned']
        self.ignored = results['files_ignored']
        self.scan_duration = results['scan_duration']
        self.scan_id = results.get('scan_id', 'N/A')
        self.findings: List[Finding] = []
        
        from archon.modules.settings_manager import load_config
        self.config = load_config(self.root_path / "archon-config.json")

    def _find_last_scan_folder(self) -> Optional[Path]:
        try:
            archon_one_root = self.output_root.parent.parent
            if not archon_one_root.exists():
                return None
            dirs = [d for d in archon_one_root.iterdir() if d.is_dir()]
            dirs = sorted(dirs, key=lambda x: x.name)
            current_name = self.output_root.parent.name
            current_index = -1
            for idx, d in enumerate(dirs):
                if d.name == current_name:
                    current_index = idx
                    break
            if current_index <= 0:
                return None
            prev_folder = dirs[current_index - 1] / "02_security"
            if prev_folder.exists():
                return prev_folder
        except Exception:
            pass
        return None

    def _load_previous_summary(self) -> Dict[str, Any]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return {}
        summary_json = prev_folder / "01_security_summary.json"
        if summary_json.exists():
            try:
                return json.loads(summary_json.read_text(encoding='utf-8'))
            except Exception:
                pass
        return {}

    def _load_previous_findings(self) -> List[Dict[str, Any]]:
        prev_folder = self._find_last_scan_folder()
        if not prev_folder:
            return []
        
        all_prev_findings = []
        for name in [
            "02_secrets.json", "03_credentials.json", "04_insecure_functions.json",
            "05_web_security.json", "06_crypto_security.json", "07_dependency_security.json",
            "08_configuration_security.json", "09_sensitive_files.json"
        ]:
            p = prev_folder / name
            if p.exists():
                try:
                    data = json.loads(p.read_text(encoding='utf-8'))
                    # Reports 02-09 list their main findings under key matching report topic
                    # E.g. "secrets", "credentials", "insecure_functions"
                    key = name.split('.')[0][3:]  # strip '02_' and '.json'
                    findings_list = data.get(key, [])
                    if not findings_list and isinstance(data, list):
                        findings_list = data
                    all_prev_findings.extend(findings_list)
                except Exception:
                    pass
        return all_prev_findings

    def generate_reports(self):
        self.output_root.mkdir(parents=True, exist_ok=True)
        self._run_security_audit()
        
        # Filter findings by minimum severity from config
        min_sev = self.config.get('security', {}).get('minimum_severity', 'Low')
        severity_ranks = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}
        min_rank = severity_ranks.get(min_sev, 1)
        self.findings = [f for f in self.findings if severity_ranks.get(f.severity, 1) >= min_rank]
        
        # Write reports
        self._report_02_secrets()
        self._report_03_credentials()
        self._report_04_insecure_functions()
        self._report_05_web_security()
        self._report_06_crypto_security()
        self._report_07_dependency_security()
        self._report_08_configuration_security()
        self._report_09_sensitive_files()
        self._report_10_scan_metadata()
        
        # Generate summary last as it collects statistics
        self._report_01_summary()
        
        # Generate interactive HTML report
        from archon.core.html_generator import compile_and_write_html_report
        nav = {"prev": "../01_metrics/report.html", "next": "../03_Code_Analysis/report.html"}
        compile_and_write_html_report(self.output_root, self.results, "Security Checkers (Module 02)", nav)

    def _get_footer(self) -> str:
        local_time = time.localtime(self.results.get('start_time', time.time()))
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
        return (
            "\n\n=========================================\n"
            "Generated by Archon One Security\n"
            "Version: 0.1.0\n"
            f"Scan ID: {self.scan_id}\n"
            f"Repository Name: {self.root_path.name}\n"
            f"Timestamp: {timestamp_str}\n"
            f"Total Scan Duration: {self.scan_duration:.4f} seconds\n"
            "=========================================\n"
        )

    def _write_files(self, base_name: str, txt_content: str, json_data: Any):
        self.output_root.mkdir(parents=True, exist_ok=True)
        txt_content_with_footer = txt_content + self._get_footer()
        
        if self.config.get('output', {}).get('txt', True):
            txt_path = self.output_root / f"{base_name}.txt"
            txt_path.write_text(txt_content_with_footer, encoding='utf-8')
            
        if self.config.get('output', {}).get('json', True):
            json_path = self.output_root / f"{base_name}.json"
            json_path.write_text(json.dumps(json_data, indent=2), encoding='utf-8')
            
        if self.config.get('output', {}).get('md', True):
            md_path = self.output_root / f"{base_name}.md"
            md_content = f"# Archon One Report - {base_name.replace('_', ' ').title()}\n\n```txt\n{txt_content_with_footer}\n```\n"
            md_path.write_text(md_content, encoding='utf-8')

    def _mask_secret(self, secret: str) -> str:
        if len(secret) <= 6:
            return "*" * len(secret)
        return secret[:3] + "..." + secret[-3:]

    def _run_security_audit(self):
        """Runs security scans across all indexed files."""
        # 1. Audit scanned source/text files
        for f in self.scanned:
            filepath = self.root_path / f['file']
            if not filepath.exists() or not filepath.is_file():
                continue
                
            try:
                content = filepath.read_text(encoding='utf-8')
            except Exception:
                try:
                    content = filepath.read_text(encoding='latin-1')
                except Exception:
                    continue

            self._scan_file_content(f['file'], content)
            
        # 2. Audit all files (scanned and ignored) for sensitive file path checks
        all_items = self.scanned + self.ignored
        for item in all_items:
            self._scan_file_path_for_sensitive_files(item)

        # 3. Additional audits
        self._run_best_practices_and_license_audit()
        self._run_file_permissions_audit()

    def _mask_value_if_needed(self, val: str) -> str:
        return self._mask_secret(val)

    def _scan_file_content(self, file_path: str, content: str):
        lines = content.splitlines()
        p = Path(file_path)
        ext = p.suffix.lower()
        filename = p.name.lower()
        
        # Multi-line secrets scan
        self._scan_multiline_secrets(file_path, content)

        # Run container security scan if Docker/Compose
        self._scan_container_security(file_path, content)
        
        # Run Gitignore scanner
        self._scan_gitignore_security(file_path, content)
        
        # Run CI/CD workflow scanner
        self._scan_cicd_security(file_path, content)

        # Line-by-line scans
        for idx, line in enumerate(lines, 1):
            stripped_line = line.strip()
            if not stripped_line:
                continue

            self._scan_secrets_on_line(file_path, idx, stripped_line)
            self._scan_credentials_on_line(file_path, idx, stripped_line)
            self._scan_insecure_functions_on_line(file_path, idx, stripped_line, ext)
            self._scan_web_security_on_line(file_path, idx, stripped_line)
            self._scan_crypto_security_on_line(file_path, idx, stripped_line)
            self._scan_configuration_on_line(file_path, idx, stripped_line, filename)
            self._scan_additional_globals_on_line(file_path, idx, stripped_line)
            self._scan_logging_security_on_line(file_path, idx, stripped_line)
            self._scan_unsafe_file_operations_on_line(file_path, idx, stripped_line)

    def _scan_multiline_secrets(self, file_path: str, content: str):
        # Private Keys
        private_key_regex = re.compile(r'-----BEGIN (RSA |EC |PGP |OPENSSH )?PRIVATE KEY-----')
        if private_key_regex.search(content):
            self.findings.append(Finding(
                file=file_path,
                line=1,
                severity="Critical",
                category="Secrets",
                issue_type="Private Key Committed",
                matched_pattern="-----BEGIN ... PRIVATE KEY-----",
                masked_value="[PRIVATE KEY BLOCK]",
                recommendation="Remove the private key from source control immediately. Use an environment variable or vault.",
                line_content="-----BEGIN PRIVATE KEY-----"
            ))

    def _scan_secrets_on_line(self, file_path: str, line_num: int, line: str):
        # 1. Google API Key
        google_key = re.search(r'\b(AIzaSy[A-Za-z0-9-_]{33})\b', line)
        if google_key:
            self.findings.append(Finding(
                file=file_path,
                line=line_num,
                severity="Critical",
                category="Secrets",
                issue_type="Google API Key",
                matched_pattern=google_key.group(1),
                masked_value=self._mask_secret(google_key.group(1)),
                recommendation="Revoke the Google API key immediately and store it as a secure secret.",
                line_content=line
            ))

        # 2. OpenAI API Key
        openai_key = re.search(r'\b(sk-[a-zA-Z0-9]{20,}|sk-proj-[a-zA-Z0-9_-]{48,})\b', line)
        if openai_key:
            self.findings.append(Finding(
                file=file_path,
                line=line_num,
                severity="Critical",
                category="Secrets",
                issue_type="OpenAI API Key",
                matched_pattern=openai_key.group(1),
                masked_value=self._mask_secret(openai_key.group(1)),
                recommendation="Revoke the OpenAI API key immediately and rotate your secret tokens.",
                line_content=line
            ))

        # 3. AWS Access Key
        aws_key = re.search(r'\b(AKIA[0-9A-Z]{16})\b', line)
        if aws_key:
            self.findings.append(Finding(
                file=file_path,
                line=line_num,
                severity="Critical",
                category="Secrets",
                issue_type="AWS Access Key ID",
                matched_pattern=aws_key.group(1),
                masked_value=self._mask_secret(aws_key.group(1)),
                recommendation="Revoke the AWS Access Key ID. Use AWS IAM Roles or Secrets Manager.",
                line_content=line
            ))

        # 4. GitHub Token
        github_token = re.search(r'\b(ghp_[0-9a-zA-Z]{36}|github_pat_[0-9a-zA-Z_]{82})\b', line)
        if github_token:
            self.findings.append(Finding(
                file=file_path,
                line=line_num,
                severity="Critical",
                category="Secrets",
                issue_type="GitHub Token",
                matched_pattern=github_token.group(1),
                masked_value=self._mask_secret(github_token.group(1)),
                recommendation="Revoke the GitHub Personal Access Token and regenerate a new token.",
                line_content=line
            ))

        # 5. Slack Token
        slack_token = re.search(r'\b(xox[baprs]-[0-9a-zA-Z]{10,})\b', line)
        if slack_token:
            self.findings.append(Finding(
                file=file_path,
                line=line_num,
                severity="Critical",
                category="Secrets",
                issue_type="Slack Token",
                matched_pattern=slack_token.group(1),
                masked_value=self._mask_secret(slack_token.group(1)),
                recommendation="Revoke the Slack Token and update your integration configs.",
                line_content=line
            ))

        # 6. Stripe Key
        stripe_key = re.search(r'\b(sk_live_[0-9a-zA-Z]{24})\b', line)
        if stripe_key:
            self.findings.append(Finding(
                file=file_path,
                line=line_num,
                severity="Critical",
                category="Secrets",
                issue_type="Stripe Secret Key",
                matched_pattern=stripe_key.group(1),
                masked_value=self._mask_secret(stripe_key.group(1)),
                recommendation="Revoke the Stripe Secret Key immediately in the Stripe dashboard.",
                line_content=line
            ))

        # 7. Database Connection String with Credentials
        db_conn = re.search(r'\b(mongodb(?:\+srv)?|postgres(?:ql)?|mysql)://([^:]+):([^@]+)@', line)
        if db_conn:
            self.findings.append(Finding(
                file=file_path,
                line=line_num,
                severity="Critical",
                category="Secrets",
                issue_type="Database Connection String Credentials",
                matched_pattern=db_conn.group(0),
                masked_value=f"{db_conn.group(1)}://{db_conn.group(2)}:***@{line.split('@')[-1][:15]}...",
                recommendation="Remove hardcoded credentials from the connection string. Inject them via environment variables.",
                line_content=line
            ))

        # 8. Authorization Header Token
        auth_token = re.search(r'\b(Authorization|Auth-Token|X-Auth-Token)\s*[:=]\s*[\'"](Bearer|Basic|Token)?\s*([a-zA-Z0-9_\-\.]{15,})[\'"]', line, re.IGNORECASE)
        if auth_token:
            self.findings.append(Finding(
                file=file_path,
                line=line_num,
                severity="Critical",
                category="Secrets",
                issue_type="Hardcoded Authorization Token",
                matched_pattern=auth_token.group(3),
                masked_value=self._mask_secret(auth_token.group(3)),
                recommendation="Do not hardcode auth tokens or bearer credentials. Retrieve them dynamically at runtime.",
                line_content=line
            ))

    def _scan_credentials_on_line(self, file_path: str, line_num: int, line: str):
        # Match assignments to password-like variables
        pw_match = re.search(
            r'\b(db_password|database_pwd|mysql_password|pg_password|redis_password|ftp_password|smtp_password|mail_password|admin_password|root_password|secret_password|user_password|auth_password|pass_word)\s*[:=]\s*[\'"]([^\'"]+)[\'"]', 
            line, 
            re.IGNORECASE
        )
        if pw_match:
            var_name = pw_match.group(1)
            val = pw_match.group(2)
            
            # Filter trivial placeholders / templates
            placeholders = {"", "password", "123456", "admin", "root", "secret", "null", "none", "placeholder", "changeme", "change_me", "todo", "test", "mysecretpassword", "dummy", "n/a"}
            if val.lower() not in placeholders and not re.search(r'[\{\}\$]', val):
                self.findings.append(Finding(
                    file=file_path,
                    line=line_num,
                    severity="Critical",
                    category="Credentials",
                    issue_type="Hardcoded Password",
                    matched_pattern=f"{var_name} = '{val}'",
                    masked_value=f"{var_name} = '{self._mask_secret(val)}'",
                    recommendation="Remove the hardcoded password value. Load it from configurations or environment variables.",
                    line_content=line
                ))

        # Match hardcoded root/admin usernames
        user_match = re.search(
            r'\b(admin_user|root_user|db_user|ftp_user|smtp_user)\s*[:=]\s*[\'"](root|admin|administrator|sa|mailadmin)[\'"]', 
            line, 
            re.IGNORECASE
        )
        if user_match:
            var_name = user_match.group(1)
            val = user_match.group(2)
            self.findings.append(Finding(
                file=file_path,
                line=line_num,
                severity="Medium",
                category="Credentials",
                issue_type="Hardcoded Admin Username",
                matched_pattern=f"{var_name} = '{val}'",
                masked_value=f"{var_name} = '{val}'",
                recommendation="Avoid hardcoding default username credentials in application files.",
                line_content=line
            ))

    def _scan_insecure_functions_on_line(self, file_path: str, line_num: int, line: str, ext: str):
        if ext == '.py':
            if 'eval(' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Medium", category="Insecure Functions",
                    issue_type="Python eval() Use", matched_pattern="eval(", masked_value="eval(",
                    recommendation="Avoid using eval(), which can execute arbitrary python expressions. Parse using ast.literal_eval or json.loads.",
                    line_content=line
                ))
            if 'exec(' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="High", category="Insecure Functions",
                    issue_type="Python exec() Use", matched_pattern="exec(", masked_value="exec(",
                    recommendation="Avoid using exec(). It enables arbitrary python code executions.",
                    line_content=line
                ))
            if 'pickle.loads(' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="High", category="Insecure Functions",
                    issue_type="Python pickle Deserialization", matched_pattern="pickle.loads(", masked_value="pickle.loads(",
                    recommendation="Pickle loads is unsafe. Use json or protobuf serializers for untrusted data input.",
                    line_content=line
                ))
            if 'os.system(' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Medium", category="Insecure Functions",
                    issue_type="Python os.system() Use", matched_pattern="os.system(", masked_value="os.system(",
                    recommendation="Avoid os.system(). Use the subprocess module with shell=False.",
                    line_content=line
                ))
            if 'shell=True' in line and 'subprocess' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="High", category="Insecure Functions",
                    issue_type="Subprocess With shell=True", matched_pattern="shell=True", masked_value="shell=True",
                    recommendation="Set shell=False and pass arguments as a list to avoid command injection vulnerabilities.",
                    line_content=line
                ))
            if 'tempfile.mktemp(' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Medium", category="Insecure Functions",
                    issue_type="Unsafe Temp File Creation", matched_pattern="tempfile.mktemp(", masked_value="tempfile.mktemp(",
                    recommendation="Use tempfile.TemporaryFile or mkstemp which prevents file race conditions.",
                    line_content=line
                ))
            if 'yaml.load(' in line and 'Loader' not in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="High", category="Insecure Functions",
                    issue_type="Unsafe YAML Load", matched_pattern="yaml.load(", masked_value="yaml.load(",
                    recommendation="Use yaml.safe_load() to prevent arbitrary custom object instantiation.",
                    line_content=line
                ))
        elif ext in ('.js', '.ts', '.jsx', '.tsx'):
            if 'eval(' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="High", category="Insecure Functions",
                    issue_type="JS eval() Use", matched_pattern="eval(", masked_value="eval(",
                    recommendation="Avoid eval() since it evaluates arbitrary strings as executable JavaScript code.",
                    line_content=line
                ))
            if 'new Function(' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Medium", category="Insecure Functions",
                    issue_type="JS Function Constructor", matched_pattern="new Function(", masked_value="new Function(",
                    recommendation="Avoid new Function(). It acts like eval().",
                    line_content=line
                ))
            if 'document.write(' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Medium", category="Insecure Functions",
                    issue_type="JS document.write() Use", matched_pattern="document.write(", masked_value="document.write(",
                    recommendation="Avoid document.write(). Use createElement or DOM APIs.",
                    line_content=line
                ))
            if 'innerHTML' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Low", category="Insecure Functions",
                    issue_type="JS innerHTML Assignment", matched_pattern="innerHTML", masked_value="innerHTML",
                    recommendation="Use textContent or innerText to prevent Cross-Site Scripting (XSS).",
                    line_content=line
                ))
        elif ext == '.php':
            if 'eval(' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="High", category="Insecure Functions",
                    issue_type="PHP eval() Use", matched_pattern="eval(", masked_value="eval(",
                    recommendation="Avoid using eval() in PHP.",
                    line_content=line
                ))
            if re.search(r'\b(exec|system|shell_exec|passthru)\(', line):
                func = re.search(r'\b(exec|system|shell_exec|passthru)\(', line).group(1)
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="High", category="Insecure Functions",
                    issue_type=f"PHP System Execution ({func})", matched_pattern=f"{func}(", masked_value=f"{func}(",
                    recommendation="Avoid invoking system commands in PHP. Sanitize input with escapeshellarg().",
                    line_content=line
                ))
        elif ext == '.java':
            if 'Runtime.getRuntime().exec(' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="High", category="Insecure Functions",
                    issue_type="Java Runtime.exec()", matched_pattern="Runtime.getRuntime().exec(", masked_value="Runtime.getRuntime().exec(",
                    recommendation="Avoid dynamic runtime system invocation. Validate input parameter values carefully.",
                    line_content=line
                ))
            if 'new ObjectInputStream(' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="High", category="Insecure Functions",
                    issue_type="Java Object Deserialization", matched_pattern="ObjectInputStream", masked_value="ObjectInputStream",
                    recommendation="Do not deserialize untrusted data stream inputs.",
                    line_content=line
                ))
        elif ext in ('.c', '.cpp', '.h', '.hpp'):
            if re.search(r'\bgets\s*\(', line):
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="High", category="Insecure Functions",
                    issue_type="C gets() Use", matched_pattern="gets(", masked_value="gets(",
                    recommendation="gets() is deprecated and vulnerable to buffer overflow. Use fgets().",
                    line_content=line
                ))
            if re.search(r'\bstrcpy\s*\(', line):
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Medium", category="Insecure Functions",
                    issue_type="C strcpy() Use", matched_pattern="strcpy(", masked_value="strcpy(",
                    recommendation="strcpy() has no length check bounds. Use strncpy().",
                    line_content=line
                ))
            if re.search(r'\bsprintf\s*\(', line):
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Medium", category="Insecure Functions",
                    issue_type="C sprintf() Use", matched_pattern="sprintf(", masked_value="sprintf(",
                    recommendation="sprintf() can cause buffer overflow. Use snprintf().",
                    line_content=line
                ))

    def _scan_web_security_on_line(self, file_path: str, line_num: int, line: str):
        # 1. SQL Injection indicators
        sql_conc = re.search(r'(execute|query|select|db_exec)\(.*?\b(select|where|insert|update|delete)\b.*?(?:\+\s*\w+|\%\s*\(|\{\w+\})', line, re.IGNORECASE)
        if sql_conc:
            self.findings.append(Finding(
                file=file_path, line=line_num, severity="High", category="Web Security",
                issue_type="Potential SQL Injection", matched_pattern=sql_conc.group(0)[:30], masked_value="...",
                recommendation="Use parameterized SQL queries or ORMs rather than concatenating user strings directly.",
                line_content=line
            ))

        # 2. XXE Vulnerability Detection
        if 'import xml.' in line or 'import defusedxml' in line:
            if 'import xml.etree' in line or 'import xml.dom' in line or 'import xml.sax' in line:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Medium", category="Web Security",
                    issue_type="Potential XXE Vulnerability", matched_pattern="XML Parser Import", masked_value="...",
                    recommendation="Use 'defusedxml' package instead of standard 'xml' library to prevent XML External Entity (XXE) attacks.",
                    line_content=line
                ))

        # 2. HTTP URL endpoints
        http_url = re.search(r'[\'"](http://[a-zA-Z0-9\-_\.]+)(?!\.org|\.gov|\.edu|\.net/pyproject)[\'"]', line)
        if http_url:
            url = http_url.group(1)
            if not any(x in url for x in ["localhost", "127.0.0.1", "0.0.0.0", "example.com", "schema.org"]):
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Low", category="Web Security",
                    issue_type="Insecure HTTP Url", matched_pattern=url, masked_value=url,
                    recommendation="Change http:// schema links to secure https:// counterparts.",
                    line_content=line
                ))

        # 3. Weak CORS origins wildcard
        cors_wild = re.search(r'Access-Control-Allow-Origin.*?\*', line)
        if cors_wild:
            self.findings.append(Finding(
                file=file_path, line=line_num, severity="Medium", category="Web Security",
                issue_type="Wildcard CORS Policy", matched_pattern="CORS * wildcard", masked_value="*",
                recommendation="Avoid Access-Control-Allow-Origin: * for authenticated interfaces. Use explicit origin bounds.",
                line_content=line
            ))

    def _scan_crypto_security_on_line(self, file_path: str, line_num: int, line: str):
        # 1. MD5 Usage
        if re.search(r'\b(md5|hashlib\.md5)\b', line, re.IGNORECASE) and 'import' not in line:
            self.findings.append(Finding(
                file=file_path, line=line_num, severity="Medium", category="Cryptography",
                issue_type="Broken Cryptographic Hash (MD5)", matched_pattern="MD5", masked_value="MD5",
                recommendation="MD5 is cryptographically weak. Upgrade to SHA-256 or bcrypt for password stores.",
                line_content=line
            ))

        # 2. SHA1 Usage
        if re.search(r'\b(sha1|hashlib\.sha1)\b', line, re.IGNORECASE) and 'import' not in line:
            self.findings.append(Finding(
                file=file_path, line=line_num, severity="Medium", category="Cryptography",
                issue_type="Weak Cryptographic Hash (SHA-1)", matched_pattern="SHA-1", masked_value="SHA-1",
                recommendation="SHA-1 is weak and subject to collisions. Use SHA-256 or SHA-512 instead.",
                line_content=line
            ))

        # 3. Weak Symmetric Encryption (DES)
        if re.search(r'\b(des|DES\.new)\b', line) and 'import' not in line:
            self.findings.append(Finding(
                file=file_path, line=line_num, severity="High", category="Cryptography",
                issue_type="Weak Cipher (DES)", matched_pattern="DES", masked_value="DES",
                recommendation="DES and TripleDES are obsolete. Replace with AES encryption algorithm.",
                line_content=line
            ))

        # 4. ECB block mode configuration
        if 'MODE_ECB' in line:
            self.findings.append(Finding(
                file=file_path, line=line_num, severity="High", category="Cryptography",
                issue_type="Insecure ECB Cipher Mode", matched_pattern="MODE_ECB", masked_value="MODE_ECB",
                recommendation="ECB mode leaks plaintext distribution details. Replace with CBC or GCM block mode.",
                line_content=line
            ))

        # 5. Math.random / random.random in security variables
        rand_match = re.search(r'\b(secret|token|key|password|passwd|salt)\b.*?(Math\.random|random\.random|random\.randint)', line, re.IGNORECASE)
        if rand_match:
            self.findings.append(Finding(
                file=file_path, line=line_num, severity="Low", category="Cryptography",
                issue_type="Weak Pseudo-Random Number Generator", matched_pattern=rand_match.group(2), masked_value=rand_match.group(2),
                recommendation="Use crytographically secure random generators (e.g., Python 'secrets' module, Web Crypto API) for keys/tokens.",
                line_content=line
            ))

    def _scan_configuration_on_line(self, file_path: str, line_num: int, line: str, filename: str):
        # Django / Flask Debug Enabled
        if 'debug' in filename or file_path.endswith('.py') or file_path.endswith('.settings'):
            dbg = re.search(r'\b(DEBUG|FLASK_DEBUG)\s*=\s*(True|1)', line, re.IGNORECASE)
            if dbg:
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="High", category="Configuration Security",
                    issue_type="Debug Mode Enabled in Code", matched_pattern=dbg.group(0), masked_value=dbg.group(2),
                    recommendation="Ensure debug mode settings are turned off in staging and production environment files.",
                    line_content=line
                ))

        # Hardcoded Host IP addresses
        ip_match = re.search(r'\b((?:[0-9]{1,3}\.){3}[0-9]{1,3})\b', line)
        if ip_match:
            ip = ip_match.group(1)
            if not any(ip.startswith(x) for x in ["127.", "0.0.", "255.", "8.8.8.8", "1.1.1.1"]):
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Low", category="Configuration Security",
                    issue_type="Hardcoded IP Address", matched_pattern=ip, masked_value=ip,
                    recommendation="Replace hardcoded system host IPs with DNS hostnames or configuration properties.",
                    line_content=line
                ))

    def _scan_additional_globals_on_line(self, file_path: str, line_num: int, line: str):
        # 1. Key comment indicators
        cmt_match = re.search(r'(#|//)\s*\b(TODO|FIXME|HACK|BUG|SECURITY)\b', line, re.IGNORECASE)
        if cmt_match:
            tag = cmt_match.group(2).upper()
            self.findings.append(Finding(
                file=file_path, line=line_num, severity="Informational", category="General",
                issue_type=f"Review Tag ({tag})", matched_pattern=tag, masked_value=tag,
                recommendation=f"Review the noted code comment issue block associated with {tag}.",
                line_content=line
            ))

        # 2. PAN/Aadhaar/Credit Card pattern leaks
        aadhaar = re.search(r'\b[2-9]\d{3}\s\d{4}\s\d{4}\b', line)
        if aadhaar:
            self.findings.append(Finding(
                file=file_path, line=line_num, severity="High", category="Secrets",
                issue_type="Aadhaar Card Pattern Leak", matched_pattern="Aadhaar", masked_value=self._mask_secret(aadhaar.group(0)),
                recommendation="Remove Aadhaar number patterns from test files or committed static contents.",
                line_content=line
            ))

        pan = re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b', line)
        if pan:
            self.findings.append(Finding(
                file=file_path, line=line_num, severity="High", category="Secrets",
                issue_type="PAN Card Pattern Leak", matched_pattern="PAN Number", masked_value=self._mask_secret(pan.group(0)),
                recommendation="Avoid committing PAN card credentials.",
                line_content=line
            ))

        cc = re.search(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|6(?:011|5[0-9]{2})[0-9]{12}|3[47][0-9]{13})\b', line)
        if cc:
            self.findings.append(Finding(
                file=file_path, line=line_num, severity="High", category="Secrets",
                issue_type="Credit Card Leak", matched_pattern="Credit Card", masked_value=self._mask_secret(cc.group(0)),
                recommendation="Rotate leaking credit card numbers and purge database/test configurations.",
                line_content=line
            ))

        # Email Leak
        email = re.search(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', line)
        if email:
            addr = email.group(1)
            if not any(x in addr.lower() for x in ["example.com", "test.com", "domain.com", "user@"]):
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Informational", category="General",
                    issue_type="Committed Email Address", matched_pattern=addr, masked_value=addr,
                    recommendation="Confirm if this email address belongs in committed repository logs.",
                    line_content=line
                ))

    def _scan_file_path_for_sensitive_files(self, item: Dict[str, Any]):
        file_path = item['file']
        p = Path(file_path)
        name = p.name.lower()
        ext = p.suffix.lower()
        
        # Check private keys
        if ext in ('.pem', '.key', '.pkcs8', '.p12', '.keystore') or 'id_rsa' in name or 'id_dsa' in name or 'id_ed25519' in name:
            self.findings.append(Finding(
                file=file_path, line=1, severity="Critical", category="Sensitive Files",
                issue_type="Committed Private Key or Keystore File", matched_pattern=name, masked_value=name,
                recommendation="Remove this private key or keystore file immediately from git history. Revoke key pairs and credentials.",
                line_content=file_path
            ))
        # Database Dumps
        elif ext in ('.sql', '.sqlite', '.db', '.dump') or name.endswith('.db.gz'):
            if any(x in name for x in ["backup", "dump", "export", "mysql", "postgres"]):
                self.findings.append(Finding(
                    file=file_path, line=1, severity="High", category="Sensitive Files",
                    issue_type="Committed Database Backup", matched_pattern=name, masked_value=name,
                    recommendation="Remove database backup dump files from the source repository.",
                    line_content=file_path
                ))
        # Environment files and credentials configs
        elif name == '.env' or name.startswith('.env.') or name in ('credentials.json', 'firebase-admin.json', 'aws-credentials', 'docker-compose.override.yml'):
            self.findings.append(Finding(
                file=file_path, line=1, severity="High", category="Sensitive Files",
                issue_type="Committed Configuration or Credentials File", matched_pattern=name, masked_value=name,
                recommendation="Add credentials and local configuration files to .gitignore immediately. Secrets must not be committed.",
                line_content=file_path
            ))
        # Swap / temp files
        elif ext in ('.swp', '.tmp', '.bak', '.old'):
            self.findings.append(Finding(
                file=file_path, line=1, severity="Low", category="Sensitive Files",
                issue_type="Committed Temporary or Backup File", matched_pattern=name, masked_value=name,
                recommendation="Clean up backup files and swp structures. Standardize .gitignore patterns.",
                line_content=file_path
            ))

    def _get_category_findings(self, category: str) -> List[Finding]:
        """Returns findings filtered by category and sorted by severity."""
        filtered = [f for f in self.findings if f.category == category]
        return sorted(filtered, key=lambda x: (SEVERITY_ORDER.get(x.severity, 99), x.file, x.line))

    def _write_findings_report(self, report_num: str, category_name: str, category_key: str, headers: List[str], row_extractor):
        """Generates TXT and JSON reports for findings under a specific category."""
        category_findings = self._get_category_findings(category_name)
        
        # Load previous scan findings for delta diff comparisons
        prev_list = self._load_previous_findings()
        prev_sigs = {f"{item.get('file')}:{item.get('category')}:{item.get('issue_type')}:{item.get('matched_pattern')}" for item in prev_list}
        
        # Extend headers to include a status column if a previous scan is available
        actual_headers = list(headers)
        if prev_list:
            actual_headers.append("Status")
            
        rows_txt = []
        rows_json = []
        
        for f in category_findings:
            row = row_extractor(f)
            item_json = f.to_dict()
            
            if prev_list:
                status = "None"
                if f.get_signature() not in prev_sigs:
                    status = "[NEW]"
                row.append(status)
                item_json["change_since_last_scan"] = status
                
            rows_txt.append(row)
            rows_json.append(item_json)

        txt = []
        txt.append("=========================================")
        txt.append(f"          {report_num} {category_name.upper()} REPORT         ")
        txt.append("=========================================\n")
        
        if prev_list:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append(f"## {category_name} Detections Detailed")
        if rows_txt:
            txt.append(tabulate(rows_txt, headers=actual_headers, tablefmt="grid"))
        else:
            txt.append(f"No {category_name.lower()} vulnerabilities found in this repository.")
            
        # Resolved findings detection (present in previous scan under this category, but no longer here)
        if prev_list:
            curr_sigs = {f.get_signature() for f in self.findings}
            resolved_txt = []
            resolved_json = []
            for item in prev_list:
                if item.get('category') == category_name:
                    sig = f"{item.get('file')}:{item.get('category')}:{item.get('issue_type')}:{item.get('matched_pattern')}"
                    if sig not in curr_sigs:
                        resolved_txt.append([
                            item.get('file'),
                            item.get('line'),
                            item.get('issue_type'),
                            item.get('severity'),
                            item.get('recommendation')
                        ])
                        resolved_json.append(item)
                        
            txt.append(f"\n## Resolved {category_name} Issues Since Last Scan")
            if resolved_txt:
                txt.append(tabulate(resolved_txt, headers=["File", "Line", "Issue Type", "Severity", "Recommendation"], tablefmt="grid"))
            else:
                txt.append("No previously flagged issues were resolved in this scan.")

        json_data = {
            category_key: rows_json
        }
        if prev_list:
            json_data["resolved_issues"] = resolved_json
            
        self._write_files(f"{report_num}_{category_key}", "\n".join(txt), json_data)

    def _report_02_secrets(self):
        def extractor(f: Finding):
            masked_line = f.line_content.replace(f.matched_pattern, f.masked_value) if f.matched_pattern in f.line_content else f.line_content
            if len(masked_line) > 60:
                masked_line = masked_line[:57] + "..."
            return [f.file, f.line, f.issue_type, f.severity, masked_line, f.recommendation]
        self._write_findings_report(
            "02", "Secrets", "secrets", 
            ["File", "Line", "Secret Type", "Severity", "Masked Snippet", "Recommendation"], 
            extractor
        )

    def _report_03_credentials(self):
        def extractor(f: Finding):
            masked_line = f.line_content
            if f.matched_pattern in masked_line:
                masked_line = masked_line.replace(f.matched_pattern, f.masked_value)
            if len(masked_line) > 60:
                masked_line = masked_line[:57] + "..."
            return [f.file, f.line, f.issue_type, f.severity, masked_line, f.recommendation]
        self._write_findings_report(
            "03", "Credentials", "credentials", 
            ["File", "Line", "Credential Type", "Severity", "Masked Snippet", "Recommendation"], 
            extractor
        )

    def _report_04_insecure_functions(self):
        def extractor(f: Finding):
            snippet = f.line_content
            if len(snippet) > 60:
                snippet = snippet[:57] + "..."
            return [f.file, f.line, f.issue_type, f.severity, snippet, f.recommendation]
        self._write_findings_report(
            "04", "Insecure Functions", "insecure_functions", 
            ["File", "Line", "Insecure Call / Function", "Severity", "Code Snippet", "Recommendation"], 
            extractor
        )

    def _report_05_web_security(self):
        def extractor(f: Finding):
            snippet = f.line_content
            if len(snippet) > 60:
                snippet = snippet[:57] + "..."
            return [f.file, f.line, f.issue_type, f.severity, snippet, f.recommendation]
        self._write_findings_report(
            "05", "Web Security", "web_security", 
            ["File", "Line", "Vulnerability Area", "Severity", "Code Snippet", "Recommendation"], 
            extractor
        )

    def _report_06_crypto_security(self):
        def extractor(f: Finding):
            snippet = f.line_content
            if len(snippet) > 60:
                snippet = snippet[:57] + "..."
            return [f.file, f.line, f.issue_type, f.severity, snippet, f.recommendation]
        self._write_findings_report(
            "06", "Crypto Security", "crypto_security", 
            ["File", "Line", "Cryptographic Risk", "Severity", "Code Snippet", "Recommendation"], 
            extractor
        )

    def _report_07_dependency_security(self):
        dep_findings = []
        from archon.modules.code_metrics import CodeMetricsReporter
        metrics_reporter = CodeMetricsReporter(self.results, self.output_root)
        deps = metrics_reporter._extract_dependencies()
        
        for d in deps:
            pkg = d['package']
            ver = d['version']
            rel_path = d['file']
            
            if ver in ("*", "any", "latest"):
                f = Finding(
                    file=rel_path, line=1, severity="Low", category="Dependency Security",
                    issue_type="Wildcard Dependency Version Pin", matched_pattern=f"{pkg}=={ver}",
                    masked_value=f"{pkg}: {ver}", 
                    recommendation="Wildcard dependency versions can fetch breaking upstream revisions. Lock it to a safe version range.",
                    line_content=f"{pkg}:{ver}"
                )
                dep_findings.append(f)
            elif "git+" in ver or "git://" in ver or ver.startswith("file:"):
                f = Finding(
                    file=rel_path, line=1, severity="Low", category="Dependency Security",
                    issue_type="Unverified Dependency Origin Source", matched_pattern=f"{pkg}=={ver}",
                    masked_value=f"{pkg}: {ver}",
                    recommendation="Validate branch permissions on direct repository dependencies.",
                    line_content=f"{pkg}:{ver}"
                )
                dep_findings.append(f)

        self.findings.extend(dep_findings)
        
        def extractor(f: Finding):
            return [f.file, f.issue_type, f.severity, f.masked_value, f.recommendation]
        self._write_findings_report(
            "07", "Dependency Security", "dependency_security", 
            ["File", "Dependency Vulnerability Issue", "Severity", "Details", "Recommendation"], 
            extractor
        )

    def _report_08_configuration_security(self):
        def extractor(f: Finding):
            snippet = f.line_content
            if len(snippet) > 60:
                snippet = snippet[:57] + "..."
            return [f.file, f.line, f.issue_type, f.severity, snippet, f.recommendation]
        self._write_findings_report(
            "08", "Configuration Security", "configuration_security", 
            ["File", "Line", "Configuration Issue", "Severity", "Code Snippet", "Recommendation"], 
            extractor
        )

    def _report_09_sensitive_files(self):
        def extractor(f: Finding):
            return [f.file, f.issue_type, f.severity, f.recommendation]
        self._write_findings_report(
            "09", "Sensitive Files", "sensitive_files", 
            ["File", "Detected File Type", "Severity", "Recommendation"], 
            extractor
        )

    def _report_10_scan_metadata(self):
        """10 Scan Metadata"""
        local_time = time.localtime(self.results.get('start_time', time.time()))
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", local_time)
        
        errors = self.results.get('errors', [])
        warnings = self.results.get('warnings', [])
        
        rules_executed = 35
        rules_triggered = len(self.findings)
        
        prev_meta = self._load_previous_summary().get('scan_metadata', {})
        
        headers = ["Metadata Key", "Value"]
        if prev_meta:
            headers.append("Change")
            
        rows_txt = [
            ["Scan ID", self.scan_id] + (["N/A"] if prev_meta else []),
            ["Timestamp", timestamp_str] + (["N/A"] if prev_meta else []),
            ["Scan Duration", f"{self.scan_duration:.4f} seconds"] + ([f"{self.scan_duration - prev_meta.get('scan_duration', 0):+.4f} s"] if prev_meta else []),
            ["Archon One Version", "0.1.0"] + (["None"] if prev_meta else []),
            ["Python Version", platform.python_version()] + (["None"] if prev_meta else []),
            ["Operating System", platform.system()] + (["None"] if prev_meta else []),
            ["Repository Path", str(self.root_path)] + (["None"] if prev_meta else []),
            ["Files Scanned", len(self.scanned)] + ([f"{len(self.scanned) - prev_meta.get('files_scanned', 0):+d}"] if prev_meta else []),
            ["Directories Traversed", self.results['counts']['total_directories']] + ([f"{self.results['counts']['total_directories'] - prev_meta.get('directories_scanned', 0):+d}"] if prev_meta else []),
            ["Rules Executed", rules_executed] + (["None"] if prev_meta else []),
            ["Rules Triggered", rules_triggered] + ([f"{rules_triggered - prev_meta.get('rules_triggered', 0):+d}"] if prev_meta else []),
            ["Ignored Files", len(self.ignored)] + ([f"{len(self.ignored) - prev_meta.get('ignored_files', 0):+d}"] if prev_meta else []),
            ["Errors Encountered", len(errors)] + ([f"{len(errors) - prev_meta.get('errors', 0):+d}"] if prev_meta else []),
            ["Warnings Logged", len(warnings)] + ([f"{len(warnings) - prev_meta.get('warnings', 0):+d}"] if prev_meta else [])
        ]
        
        txt = []
        txt.append("=========================================")
        txt.append("          10 SCAN METADATA REPORT        ")
        txt.append("=========================================\n")
        
        if prev_meta:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append("## Security Run Metadata Parameters")
        txt.append(tabulate(rows_txt, headers=headers, tablefmt="grid"))
        
        json_data = {
            "scan_metadata": {
                "scan_id": self.scan_id,
                "timestamp": timestamp_str,
                "scan_duration": self.scan_duration,
                "archon_one_version": "0.1.0",
                "python_version": platform.python_version(),
                "operating_system": platform.system(),
                "repository_path": str(self.root_path),
                "files_scanned": len(self.scanned),
                "directories_scanned": self.results['counts']['total_directories'],
                "rules_executed": rules_executed,
                "rules_triggered": rules_triggered,
                "ignored_files": len(self.ignored),
                "errors": len(errors),
                "warnings": len(warnings)
            }
        }
        
        self._write_files("10_scan_metadata", "\n".join(txt), json_data)

    def _report_01_summary(self):
        """01 Security Summary"""
        severities = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0, "Informational": 0}
        categories_count = {}
        files_with_issues = set()
        
        for f in self.findings:
            severities[f.severity] = severities.get(f.severity, 0) + 1
            categories_count[f.category] = categories_count.get(f.category, 0) + 1
            files_with_issues.add(f.file)

        score = 100.0
        score -= severities["Critical"] * 20.0
        score -= severities["High"] * 10.0
        score -= severities["Medium"] * 5.0
        score -= severities["Low"] * 2.0
        score -= severities["Informational"] * 0.5
        score = max(0.0, score)
        
        if score >= 95.0:
            grade = "A"
        elif score >= 85.0:
            grade = "B"
        elif score >= 70.0:
            grade = "C"
        elif score >= 50.0:
            grade = "D"
        else:
            grade = "F"

        total_files = len(self.scanned)
        files_with_issues_count = len(files_with_issues)
        files_without_issues_count = total_files - files_with_issues_count
        
        issue_counts = {}
        for f in self.findings:
            issue_counts[f.issue_type] = issue_counts.get(f.issue_type, 0) + 1
        most_common_issue = max(issue_counts.items(), key=lambda x: x[1])[0] if issue_counts else "None"
        
        dir_counts = {}
        for f in self.findings:
            p = Path(f.file)
            d = str(p.parent) if p.parent != Path('.') else '.'
            dir_counts[d] = dir_counts.get(d, 0) + 1
        most_affected_dir = max(dir_counts.items(), key=lambda x: x[1])[0] if dir_counts else "None"
        
        lang_counts = {}
        for f in self.findings:
            f_item = next((item for item in self.scanned if item['file'] == f.file), None)
            lang = f_item['language'] if f_item else "Unknown"
            lang_counts[lang] = lang_counts.get(lang, 0) + 1
        most_affected_lang = max(lang_counts.items(), key=lambda x: x[1])[0] if lang_counts else "None"
        
        file_risk_scores = {}
        for f in self.findings:
            pts = 0
            if f.severity == "Critical":
                pts = 25
            elif f.severity == "High":
                pts = 15
            elif f.severity == "Medium":
                pts = 8
            elif f.severity == "Low":
                pts = 3
            elif f.severity == "Informational":
                pts = 1
            file_risk_scores[f.file] = file_risk_scores.get(f.file, 0) + pts
            
        highest_risk_file_val = max(file_risk_scores.items(), key=lambda x: x[1])[0] if file_risk_scores else "None"

        prev_sum = self._load_previous_summary()
        prev_overview = prev_sum.get('security_overview', {})
        
        overview_headers = ["Metric", "Value"]
        if prev_sum:
            overview_headers.append("Change")
            
        def get_diff_str_val(curr, prev):
            if not prev_sum:
                return "N/A"
            diff = curr - prev
            return f"{diff:+d}" if diff != 0 else "0"

        overview_data = [
            ["Security Score (0-100)", f"{score:.2f}"] + ([f"{score - prev_overview.get('security_score', 0):+.2f}"] if prev_sum else []),
            ["Security Grade", grade] + ([f"Changed ({prev_overview.get('security_grade', 'N/A')} -> {grade})" if prev_overview.get('security_grade') != grade else "None"] if prev_sum else []),
            ["Total Security Issues", len(self.findings)] + ([get_diff_str_val(len(self.findings), prev_overview.get('total_issues'))] if prev_sum else []),
            ["Critical Issues", severities["Critical"]] + ([get_diff_str_val(severities["Critical"], prev_overview.get('critical_issues'))] if prev_sum else []),
            ["High Issues", severities["High"]] + ([get_diff_str_val(severities["High"], prev_overview.get('high_issues'))] if prev_sum else []),
            ["Medium Issues", severities["Medium"]] + ([get_diff_str_val(severities["Medium"], prev_overview.get('medium_issues'))] if prev_sum else []),
            ["Low Issues", severities["Low"]] + ([get_diff_str_val(severities["Low"], prev_overview.get('low_issues'))] if prev_sum else []),
            ["Informational Issues", severities["Informational"]] + ([get_diff_str_val(severities["Informational"], prev_overview.get('informational_issues'))] if prev_sum else []),
            ["Files Scanned", total_files] + ([get_diff_str_val(total_files, prev_overview.get('files_scanned'))] if prev_sum else []),
            ["Files With Issues", files_with_issues_count] + (["N/A"] if prev_sum else []),
            ["Files Without Issues", files_without_issues_count] + (["N/A"] if prev_sum else []),
            ["Most Common Issue", most_common_issue] + (["N/A"] if prev_sum else []),
            ["Most Affected Directory", most_affected_dir] + (["N/A"] if prev_sum else []),
            ["Most Affected Language", most_affected_lang] + (["N/A"] if prev_sum else []),
            ["Highest Risk File", highest_risk_file_val] + (["N/A"] if prev_sum else [])
        ]

        sorted_files = sorted(file_risk_scores.items(), key=lambda x: x[1], reverse=True)[:25]
        risk_files_txt = []
        risk_files_json = []
        for rank, (file_name, r_score) in enumerate(sorted_files, 1):
            count = sum(1 for f in self.findings if f.file == file_name)
            risk_files_txt.append([rank, file_name, r_score, count])
            risk_files_json.append({
                "rank": rank,
                "file": file_name,
                "risk_score": r_score,
                "issues_count": count
            })

        sorted_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:20]
        common_issues_txt = []
        common_issues_json = []
        for rank, (issue_name, freq) in enumerate(sorted_issues, 1):
            sev = next((f.severity for f in self.findings if f.issue_type == issue_name), "Unknown")
            common_issues_txt.append([rank, issue_name, sev, freq])
            common_issues_json.append({
                "rank": rank,
                "issue_type": issue_name,
                "severity": sev,
                "frequency": freq
            })

        severity_dist_txt = []
        severity_dist_json = []
        total_issues = len(self.findings)
        for sev in ["Critical", "High", "Medium", "Low", "Informational"]:
            freq = severities[sev]
            pct = (freq / total_issues * 100) if total_issues > 0 else 0.0
            severity_dist_txt.append([sev, freq, f"{pct:.2f}%"])
            severity_dist_json.append({
                "severity": sev,
                "count": freq,
                "percentage": round(pct, 2)
            })

        lang_dist_txt = []
        lang_dist_json = []
        for lang, freq in sorted(lang_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (freq / total_issues * 100) if total_issues > 0 else 0.0
            lang_dist_txt.append([lang, freq, f"{pct:.2f}%"])
            lang_dist_json.append({
                "language": lang,
                "count": freq,
                "percentage": round(pct, 2)
            })

        dir_dist_txt = []
        dir_dist_json = []
        for d, freq in sorted(dir_counts.items(), key=lambda x: x[1], reverse=True)[:25]:
            pct = (freq / total_issues * 100) if total_issues > 0 else 0.0
            dir_dist_txt.append([d, freq, f"{pct:.2f}%"])
            dir_dist_json.append({
                "directory": d,
                "count": freq,
                "percentage": round(pct, 2)
            })

        txt = []
        txt.append("=========================================")
        txt.append("        01 SECURITY SUMMARY REPORT       ")
        txt.append("=========================================\n")
        
        if prev_sum:
            prev_folder_name = self._find_last_scan_folder().parent.name
            txt.append(f"Comparing changes since last scan: {prev_folder_name}\n")
            
        txt.append("## Security Overview")
        txt.append(tabulate(overview_data, headers=overview_headers, tablefmt="grid"))
        
        txt.append("\n## Top 25 Highest Risk Files")
        if risk_files_txt:
            txt.append(tabulate(risk_files_txt, headers=["Rank", "File", "Risk Score", "Issues Count"], tablefmt="grid"))
        else:
            txt.append("No files flagged with security issues.")
            
        txt.append("\n## Top 20 Most Common Security Issues")
        if common_issues_txt:
            txt.append(tabulate(common_issues_txt, headers=["Rank", "Security Issue", "Severity", "Frequency"], tablefmt="grid"))
        else:
            txt.append("No security issues found.")
            
        txt.append("\n## Issue Distribution By Severity")
        txt.append(tabulate(severity_dist_txt, headers=["Severity", "Count", "Percentage"], tablefmt="grid"))
        
        txt.append("\n## Issue Distribution By Language")
        if lang_dist_txt:
            txt.append(tabulate(lang_dist_txt, headers=["Language", "Count", "Percentage"], tablefmt="grid"))
        else:
            txt.append("No issue language distributions.")
            
        txt.append("\n## Issue Distribution By Directory (Top 25)")
        if dir_dist_txt:
            txt.append(tabulate(dir_dist_txt, headers=["Directory", "Count", "Percentage"], tablefmt="grid"))
        else:
            txt.append("No issue directory distributions.")

        json_data = {
            "security_overview": {
                "security_score": round(score, 2),
                "security_grade": grade,
                "total_issues": total_issues,
                "critical_issues": severities["Critical"],
                "high_issues": severities["High"],
                "medium_issues": severities["Medium"],
                "low_issues": severities["Low"],
                "informational_issues": severities["Informational"],
                "files_scanned": total_files,
                "files_with_issues": files_with_issues_count,
                "files_without_issues": files_without_issues_count,
                "most_common_issue": most_common_issue,
                "most_affected_directory": most_affected_dir,
                "most_affected_language": most_affected_lang,
                "highest_risk_file": highest_risk_file_val
            },
            "highest_risk_files": risk_files_json,
            "most_common_security_issues": common_issues_json,
            "issue_distribution_by_severity": severity_dist_json,
            "issue_distribution_by_language": lang_dist_json,
            "issue_distribution_by_directory": dir_dist_json
        }
        
        if prev_sum:
            prev_findings_list = self._load_previous_findings()
            prev_sigs = {f"{item.get('file')}:{item.get('category')}:{item.get('issue_type')}:{item.get('matched_pattern')}" for item in prev_findings_list}
            curr_sigs = {f.get_signature() for f in self.findings}
            
            introduced_json = []
            for f in self.findings:
                if f.get_signature() not in prev_sigs:
                    introduced_json.append(f.to_dict())
            
            resolved_json = []
            for item in prev_findings_list:
                sig = f"{item.get('file')}:{item.get('category')}:{item.get('issue_type')}:{item.get('matched_pattern')}"
                if sig not in curr_sigs:
                    resolved_json.append(item)
                    
            json_data["changes_since_last_scan"] = {
                "previous_scan_folder": self._find_last_scan_folder().parent.name,
                "score_change": round(score - prev_overview.get('security_score', 0), 2),
                "total_issues_change": total_issues - prev_overview.get('total_issues', 0),
                "new_issues_introduced": introduced_json,
                "resolved_issues_fixed": resolved_json
            }
            
                    
        txt.append("\n=========================================")
        txt.append("      SCORING AND GRADING METHODOLOGY    ")
        txt.append("=========================================\n")
        txt.append("1. Scoring Rules:")
        txt.append("   - Every scan starts with an initial baseline security score of 100.0.")
        txt.append("   - For each triggered security issue, a penalty is deducted from the score based on Severity:")
        txt.append("     * Critical severity:      -20.0 points")
        txt.append("     * High severity:          -10.0 points")
        txt.append("     * Medium severity:        -5.0 points")
        txt.append("     * Low severity:           -2.0 points")
        txt.append("     * Informational severity: -0.5 points")
        txt.append("   - The final score is bounded to a minimum of 0.0 points.")
        txt.append("")
        txt.append("2. Grade Map Table:")
        txt.append("   - Grade A: Score >= 95.0     (Excellent security posture)")
        txt.append("   - Grade B: Score 85.0 - 94.99 (Good posture, minor issues)")
        txt.append("   - Grade C: Score 70.0 - 84.99 (Fair posture, moderate issues)")
        txt.append("   - Grade D: Score 50.0 - 69.99 (Poor posture, significant concerns)")
        txt.append("   - Grade F: Score < 50.0      (Critical vulnerabilities present)")

        self._write_files("01_security_summary", "\n".join(txt), json_data)

    def _run_best_practices_and_license_audit(self):
        gitignore_exists = False
        security_policy_exists = False
        license_exists = False
        lock_file_exists = False
        env_example_exists = False

        for f in self.scanned + self.ignored:
            p = Path(f['file'])
            name_lower = p.name.lower()
            if name_lower == '.gitignore':
                gitignore_exists = True
            elif 'security' in name_lower and (name_lower.endswith('.md') or name_lower.endswith('.txt')):
                security_policy_exists = True
            elif 'license' in name_lower or 'copying' in name_lower:
                license_exists = True
            elif name_lower in ('package-lock.json', 'poetry.lock', 'cargo.lock', 'yarn.lock', 'pnpm-lock.yaml', 'gemfile.lock', 'pip.lock'):
                lock_file_exists = True
            elif '.env.example' in name_lower or '.env.template' in name_lower:
                env_example_exists = True

            # Scan License file content
            if 'license' in name_lower or 'copying' in name_lower:
                try:
                    content = (self.root_path / p).read_text(encoding='utf-8', errors='ignore')
                    self._check_license_compliance(f['file'], content)
                except Exception:
                    pass

        # Add best practice findings if missing
        if not gitignore_exists:
            self.findings.append(Finding(
                file=".gitignore", line=1, severity="Medium", category="Configuration Security",
                issue_type="Missing .gitignore", matched_pattern="Missing", masked_value="...",
                recommendation="Create a .gitignore file in the repository root to prevent committing build, temporary, or sensitive files.",
                line_content=""
            ))
        if not security_policy_exists:
            self.findings.append(Finding(
                file="SECURITY.md", line=1, severity="Informational", category="General",
                issue_type="Missing Security Policy", matched_pattern="Missing", masked_value="...",
                recommendation="Add a SECURITY.md file detailing how to report vulnerabilities in this repository.",
                line_content=""
            ))
        if not license_exists:
            self.findings.append(Finding(
                file="LICENSE", line=1, severity="Low", category="General",
                issue_type="Missing License File", matched_pattern="Missing", masked_value="...",
                recommendation="Include a LICENSE file in the root to define terms of usage and distribution.",
                line_content=""
            ))
        if not lock_file_exists:
            has_deps = False
            for f in self.scanned:
                if Path(f['file']).name in ('package.json', 'pyproject.toml', 'Cargo.toml', 'Gemfile', 'go.mod'):
                    has_deps = True
                    break
            if has_deps:
                self.findings.append(Finding(
                    file="Dependency Lockfile", line=1, severity="Low", category="Configuration Security",
                    issue_type="Missing Dependency Lockfile", matched_pattern="Missing", masked_value="...",
                    recommendation="Commit your dependency lockfile (e.g. package-lock.json, poetry.lock) to ensure reproducible and secure builds.",
                    line_content=""
                ))
        if not env_example_exists:
            has_env = False
            for f in self.scanned + self.ignored:
                if '.env' in Path(f['file']).name:
                    has_env = True
                    break
            if has_env:
                self.findings.append(Finding(
                    file=".env.example", line=1, severity="Low", category="Configuration Security",
                    issue_type="Missing Environment Template", matched_pattern="Missing", masked_value="...",
                    recommendation="Provide a .env.example template file to help developers configure environment setups securely.",
                    line_content=""
                ))

    def _check_license_compliance(self, file_path: str, content: str):
        content_lower = content.lower()
        detected_license = "Unknown"
        
        if "gnu general public license" in content_lower or "gpl" in content_lower:
            detected_license = "GPL"
        elif "gnu lesser general public license" in content_lower or "lgpl" in content_lower:
            detected_license = "LGPL"
        elif "gnu affero general public license" in content_lower or "agpl" in content_lower:
            detected_license = "AGPL"
        elif "mit license" in content_lower or "mit" in content_lower:
            detected_license = "MIT"
        elif "apache license" in content_lower or "apache" in content_lower:
            detected_license = "Apache"
        elif "bsd" in content_lower:
            detected_license = "BSD"
        elif "proprietary" in content_lower:
            detected_license = "Proprietary"
            
        if detected_license in ("GPL", "LGPL", "AGPL"):
            self.findings.append(Finding(
                file=file_path, line=1, severity="Informational", category="General",
                issue_type="Copyleft License Compliance Review", matched_pattern=detected_license, masked_value=detected_license,
                recommendation=f"Review the copyleft restrictions of the detected {detected_license} license if this project is for commercial use.",
                line_content=f"Detected license terms: {detected_license}"
            ))

    def _run_file_permissions_audit(self):
        import stat
        for f in self.scanned:
            filepath = self.root_path / f['file']
            if not filepath.exists():
                continue
            try:
                mode = filepath.stat().st_mode
                if mode & stat.S_IWOTH:
                    self.findings.append(Finding(
                        file=f['file'], line=1, severity="High", category="Configuration Security",
                        issue_type="World Writable File Permission", matched_pattern="World-writable permissions", masked_value="...",
                        recommendation="Remove world-writable permissions. Change file modes to S_IWUSR or restrict permissions to avoid unauthorised write actions.",
                        line_content=f"Permissions octal: {oct(stat.S_IMODE(mode))}"
                    ))
                ext = filepath.suffix.lower()
                if ext in ('.sh', '.bash', '.py', '.pl', '.rb') and not (mode & stat.S_IXUSR):
                    self.findings.append(Finding(
                        file=f['file'], line=1, severity="Informational", category="Configuration Security",
                        issue_type="Non-executable Script File", matched_pattern="Executable script lacks user execute bit", masked_value="...",
                        recommendation="If this script file is meant to be run, add the execute permission (chmod +x) for active use.",
                        line_content=f"Permissions octal: {oct(stat.S_IMODE(mode))}"
                    ))
            except Exception:
                pass

    def _scan_container_security(self, file_path: str, content: str):
        name = Path(file_path).name.lower()
        lines = content.splitlines()
        
        if name == 'dockerfile':
            user_found = False
            healthcheck_found = False
            for idx, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith('USER'):
                    user_found = True
                    if 'root' in stripped.lower():
                        self.findings.append(Finding(
                            file=file_path, line=idx, severity="High", category="Configuration Security",
                            issue_type="Docker Running as Root", matched_pattern="USER root", masked_value="...",
                            recommendation="Avoid running container processes as root. Define a dedicated non-root user and toggle execution with USER user.",
                            line_content=line
                        ))
                elif stripped.startswith('FROM'):
                    if ':latest' in stripped or ':' not in stripped:
                        self.findings.append(Finding(
                            file=file_path, line=idx, severity="Medium", category="Configuration Security",
                            issue_type="Docker Insecure Base Tag", matched_pattern=stripped, masked_value="...",
                            recommendation="Do not use the ':latest' tag for container base images. Pin specific version numbers to guarantee stable builds.",
                            line_content=line
                        ))
                elif stripped.startswith('HEALTHCHECK'):
                    healthcheck_found = True
                elif stripped.startswith('COPY'):
                    if '. .' in stripped or '/ /' in stripped:
                        self.findings.append(Finding(
                            file=file_path, line=idx, severity="Low", category="Configuration Security",
                            issue_type="Broad Docker COPY Command", matched_pattern=stripped, masked_value="...",
                            recommendation="Avoid copying all workspace files blindly. Use specific path targets or define .dockerignore mappings.",
                            line_content=line
                        ))
                        
            if not user_found:
                self.findings.append(Finding(
                    file=file_path, line=1, severity="Medium", category="Configuration Security",
                    issue_type="Docker User Not Configured", matched_pattern="Missing USER directive", masked_value="...",
                    recommendation="Dockerfile does not declare a non-root USER. The container processes will run as root by default.",
                    line_content=""
                ))
            if not healthcheck_found:
                self.findings.append(Finding(
                    file=file_path, line=1, severity="Low", category="Configuration Security",
                    issue_type="Missing Docker HEALTHCHECK Directive", matched_pattern="Missing HEALTHCHECK", masked_value="...",
                    recommendation="Implement a HEALTHCHECK instruction in the Dockerfile to monitor container running states dynamically.",
                    line_content=""
                ))
                
        elif name in ('docker-compose.yml', 'docker-compose.yaml'):
            for idx, line in enumerate(lines, 1):
                if 'privileged: true' in line.lower():
                    self.findings.append(Finding(
                        file=file_path, line=idx, severity="High", category="Configuration Security",
                        issue_type="Privileged Container Configured", matched_pattern="privileged: true", masked_value="...",
                        recommendation="Remove privileged permissions from container definitions to limit system-level exposure risks.",
                        line_content=line.strip()
                    ))

    def _scan_cicd_security(self, file_path: str, content: str):
        if not any(x in file_path.replace('\\', '/') for x in ('.github/workflows/', '.gitlab-ci.yml', 'azure-pipelines.yml')):
            return
        lines = content.splitlines()
        for idx, line in enumerate(lines, 1):
            if 'uses:' in line and '@' in line:
                action_spec = line.split('uses:')[-1].strip()
                if '@master' in action_spec or '@main' in action_spec:
                    self.findings.append(Finding(
                        file=file_path, line=idx, severity="Medium", category="Configuration Security",
                        issue_type="Unpinned GitHub Action", matched_pattern=action_spec, masked_value="...",
                        recommendation="Pin third-party GitHub Actions to a specific commit SHA (rather than branch tags like @main) to prevent supply chain tampering.",
                        line_content=line.strip()
                    ))

    def _scan_gitignore_security(self, file_path: str, content: str):
        if Path(file_path).name != '.gitignore':
            return
        content_lower = content.lower()
        targets = [
            ('.env', "Recommend ignoring environment files (*.env, .env.*) to prevent credentials exposure."),
            ('id_', "Recommend ignoring private SSH key patterns (id_rsa, id_ed25519) in .gitignore."),
            ('.pem', "Recommend ignoring certificate files (*.pem, *.crt) to avoid commits leaks.")
        ]
        for pattern, recommendation in targets:
            if pattern not in content_lower:
                self.findings.append(Finding(
                    file=file_path, line=1, severity="Medium", category="Configuration Security",
                    issue_type="Incomplete gitignore Rules", matched_pattern=pattern, masked_value="...",
                    recommendation=recommendation,
                    line_content=""
                ))

    def _scan_logging_security_on_line(self, file_path: str, line_num: int, line: str):
        if any(x in line.lower() for x in ('log', 'logger', 'console.log', 'print')):
            leak_match = re.search(r'\b(password|pwd|api_key|apikey|jwt|token|session|cc_num|credit_card|cvv)\b', line, re.IGNORECASE)
            if leak_match:
                keyword = leak_match.group(1)
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Medium", category="Cryptography",
                    issue_type="Potential Logging Security Leak", matched_pattern=keyword, masked_value="...",
                    recommendation=f"Review this logging statement. Avoid outputting potential secret details or user credentials associated with {keyword} directly to log buffers.",
                    line_content=line
                ))

    def _scan_unsafe_file_operations_on_line(self, file_path: str, line_num: int, line: str):
        if 'shutil.rmtree' in line or 'rm -rf' in line:
            self.findings.append(Finding(
                file=file_path, line=line_num, severity="Low", category="Insecure Functions",
                issue_type="Recursive Deletion Operation", matched_pattern="Recursive delete", masked_value="...",
                recommendation="Ensure recursive delete operations validate paths thoroughly to avoid accidental system wipes.",
                line_content=line
            ))
        if ('open(' in line or 'read(' in line or 'write(' in line) and ('+' in line or '%s' in line or '.format(' in line or f'f"' in line):
            if any(x in line for x in ('path', 'file', 'dir', 'name')):
                self.findings.append(Finding(
                    file=file_path, line=line_num, severity="Informational", category="Insecure Functions",
                    issue_type="Path Concatenation Detected", matched_pattern="String addition in path resolution", masked_value="...",
                    recommendation="Use path library utilities (e.g. pathlib.Path.joinpath or os.path.join) rather than string additions to protect against directory traversals.",
                    line_content=line
                ))
