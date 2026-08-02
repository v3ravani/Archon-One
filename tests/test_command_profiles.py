import unittest
import json
import shutil
from pathlib import Path
from typer.testing import CliRunner

from archon.modules.settings_manager import (
    load_config,
    DEFAULT_CONFIG,
    validate_profile_name,
    validate_profile_commands,
    validate_profile,
    import_profiles,
    export_profiles
)
from archon.cli import app, execute_profile


class TestCommandProfiles(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path.cwd() / "test_profiles_workspace"
        self.test_dir.mkdir(exist_ok=True)
        self.config_path = self.test_dir / "archon-config.json"

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_validate_profile_name(self):
        # Valid names
        valid, msg = validate_profile_name("backend")
        self.assertTrue(valid)
        self.assertEqual(msg, "")

        valid, msg = validate_profile_name("ci-build_123")
        self.assertTrue(valid)

        # Empty name
        valid, msg = validate_profile_name("")
        self.assertFalse(valid)
        self.assertIn("cannot be empty", msg)

        # Invalid characters (space or special chars)
        valid, msg = validate_profile_name("backend dev")
        self.assertFalse(valid)
        self.assertIn("only contain letters", msg)

        # Conflict with built-in command
        valid, msg = validate_profile_name("scan")
        self.assertFalse(valid)
        self.assertIn("conflicts with a built-in", msg)

    def test_validate_profile_commands(self):
        # Valid commands
        valid, msg = validate_profile_commands(["archon analyze --architecture", "archon export --html"])
        self.assertTrue(valid)

        # Empty commands list
        valid, msg = validate_profile_commands([])
        self.assertFalse(valid)

        # List containing empty string
        valid, msg = validate_profile_commands(["archon scan", ""])
        self.assertFalse(valid)

        # Self-referential command
        valid, msg = validate_profile_commands(["archon backend"], profile_name="backend")
        self.assertFalse(valid)
        self.assertIn("self-referential loop", msg)

    def test_circular_dependency_detection(self):
        existing = {
            "prof_a": ["archon prof_b"]
        }
        # prof_b calling prof_a creates a circle
        valid, msg = validate_profile("prof_b", ["archon prof_a"], existing_profiles=existing)
        self.assertFalse(valid)
        self.assertIn("Circular dependency", msg)

    def test_import_export_profiles(self):
        cfg = dict(DEFAULT_CONFIG)
        cfg["profiles"] = {
            "backend": ["archon about", "archon help"]
        }

        exported = export_profiles(cfg)
        self.assertIn("profiles", exported)
        self.assertIn("backend", exported["profiles"])

        # Test import dict format
        import_payload = {
            "profiles": {
                "frontend": ["archon help"]
            }
        }
        updated_cfg, count, errors = import_profiles(cfg, import_payload, overwrite=False)
        self.assertEqual(count, 1)
        self.assertIn("backend", updated_cfg["profiles"])
        self.assertIn("frontend", updated_cfg["profiles"])

    def test_config_persistence(self):
        cfg = load_config(self.config_path)
        self.assertIn("profiles", cfg)
        self.assertEqual(cfg["profiles"], {})

        cfg["profiles"]["custom_build"] = ["archon about"]
        self.config_path.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

        loaded = load_config(self.config_path)
        self.assertIn("custom_build", loaded["profiles"])
        self.assertEqual(loaded["profiles"]["custom_build"], ["archon about"])

    def test_cli_execute_profile(self):
        runner = CliRunner()
        # Test executing a profile command sequence directly
        cmds = ["archon about", "archon help"]
        # execute_profile uses typer.secho / Exit on error
        try:
            execute_profile("test_profile", cmds)
        except Exception as e:
            self.fail(f"execute_profile raised unexpected exception: {e}")

    def test_cli_profiles_command(self):
        runner = CliRunner()
        result = runner.invoke(app, ["profiles"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("SAVED COMMAND PROFILES", result.output)

    def test_cli_profiles_crud_commands(self):
        runner = CliRunner()
        # Add profile
        result_add = runner.invoke(app, ["profiles", "add", "myprofile", "archon scan", "archon graph"])
        self.assertEqual(result_add.exit_code, 0)
        self.assertIn("created successfully", result_add.output)

        # List profiles
        result_list = runner.invoke(app, ["profiles", "list"])
        self.assertEqual(result_list.exit_code, 0)
        self.assertIn("myprofile", result_list.output)

        # Edit profile
        result_edit = runner.invoke(app, ["profiles", "edit", "myprofile", "archon scan", "archon graph", "archon diagrams"])
        self.assertEqual(result_edit.exit_code, 0)
        self.assertIn("updated successfully", result_edit.output)

        # Delete profile
        result_del = runner.invoke(app, ["profiles", "delete", "myprofile"])
        self.assertEqual(result_del.exit_code, 0)
        self.assertIn("deleted successfully", result_del.output)


if __name__ == "__main__":
    unittest.main()
