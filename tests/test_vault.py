import unittest
import shutil
from pathlib import Path
from typer.testing import CliRunner

from archon.modules.vault import SecretVault, MAGIC_HEADER
from archon.cli import app


class TestSecretVault(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path.cwd() / "test_vault_workspace"
        self.test_dir.mkdir(exist_ok=True)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_vault_init_and_verify(self):
        vault = SecretVault(self.test_dir)
        self.assertFalse(vault.is_initialized())

        vault.init_vault("MySecretMasterPass123!")
        self.assertTrue(vault.is_initialized())

        self.assertTrue(vault.verify_password("MySecretMasterPass123!"))
        self.assertFalse(vault.verify_password("WrongPassword"))

    def test_mask_and_unmask_file(self):
        vault = SecretVault(self.test_dir)
        target_file = self.test_dir / ".env"
        original_content = "DATABASE_URL=postgres://user:secret@localhost:5432/db\nAPI_KEY=sk_live_12345"
        target_file.write_text(original_content, encoding="utf-8")

        password = "MasterPassword456!"

        # Mask file
        rel_path = vault.mask_file(target_file, password)
        self.assertEqual(rel_path, ".env")

        # Verify file content is encrypted
        file_bytes = target_file.read_bytes()
        self.assertTrue(file_bytes.startswith(MAGIC_HEADER))
        self.assertNotIn(b"sk_live_12345", file_bytes)

        # Check status
        status = vault.get_status()
        self.assertTrue(status["initialized"])
        self.assertEqual(status["protected_count"], 1)

        # Unmask with wrong password should fail
        with self.assertRaises(ValueError):
            vault.unmask_file(target_file, "WrongPass")

        # Unmask with correct password
        vault.unmask_file(target_file, password)
        restored_content = target_file.read_text(encoding="utf-8")
        self.assertEqual(restored_content, original_content)

    def test_change_password(self):
        vault = SecretVault(self.test_dir)
        target_file = self.test_dir / "credentials.json"
        original_content = '{"key": "private_secret_key"}'
        target_file.write_text(original_content, encoding="utf-8")

        old_pass = "OldMasterPassword1!"
        new_pass = "NewMasterPassword2!"

        vault.mask_file(target_file, old_pass)

        # Change password
        vault.change_password(old_pass, new_pass)

        # Verify old pass fails and new pass succeeds
        self.assertFalse(vault.verify_password(old_pass))
        self.assertTrue(vault.verify_password(new_pass))

        # Unmask with new pass
        vault.unmask_file(target_file, new_pass)
        self.assertEqual(target_file.read_text(encoding="utf-8"), original_content)

    def test_cli_vault_status(self):
        runner = CliRunner()
        result = runner.invoke(app, ["vault", "status"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("SECRET VAULT STATUS", result.output)


if __name__ == "__main__":
    unittest.main()
