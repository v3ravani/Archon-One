import os
import json
import base64
import time
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import hashlib

MAGIC_HEADER = b"ARCHON_VAULT_V1"
VERIFY_TOKEN = b"ARCHON_VAULT_VERIFY_TOKEN"
VAULT_FILENAME = "archon-vault.json"


def _derive_key(password: str, salt: bytes) -> bytes:
    """
    Derive a 256-bit (32-byte) key from the password using scrypt.
    """
    if not isinstance(password, str) or not password:
        raise ValueError("Password must be a non-empty string.")
    return hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=16384,
        r=8,
        p=1,
        maxmem=0,
        dklen=32
    )


class SecretVault:
    def __init__(self, root_dir: Optional[Path] = None):
        self.root_dir = (root_dir or Path.cwd()).resolve()
        self.vault_file = self.root_dir / VAULT_FILENAME

    def _load_metadata(self) -> Dict[str, Any]:
        if self.vault_file.exists():
            try:
                data = json.loads(self.vault_file.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    if "protected_files" not in data or not isinstance(data["protected_files"], dict):
                        data["protected_files"] = {}
                    return data
            except Exception:
                pass
        return {
            "version": 1,
            "kdf_salt": "",
            "verify_nonce": "",
            "verify_ciphertext": "",
            "protected_files": {}
        }

    def _save_metadata(self, data: Dict[str, Any]):
        self.vault_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def is_initialized(self) -> bool:
        meta = self._load_metadata()
        return bool(meta.get("kdf_salt") and meta.get("verify_ciphertext"))

    def verify_password(self, password: str) -> bool:
        if not self.is_initialized():
            return False
        meta = self._load_metadata()
        try:
            salt = base64.b64decode(meta["kdf_salt"])
            nonce = base64.b64decode(meta["verify_nonce"])
            ciphertext = base64.b64decode(meta["verify_ciphertext"])

            key = _derive_key(password, salt)
            aesgcm = AESGCM(key)
            decrypted = aesgcm.decrypt(nonce, ciphertext, None)
            return decrypted == VERIFY_TOKEN
        except Exception:
            return False

    def init_vault(self, password: str) -> bool:
        if self.is_initialized():
            if not self.verify_password(password):
                raise ValueError("Vault already initialized. Incorrect master password.")
            return True

        salt = os.urandom(16)
        nonce = os.urandom(12)
        key = _derive_key(password, salt)

        aesgcm = AESGCM(key)
        verify_ciphertext = aesgcm.encrypt(nonce, VERIFY_TOKEN, None)

        meta = self._load_metadata()
        meta["version"] = 1
        meta["kdf_salt"] = base64.b64encode(salt).decode("utf-8")
        meta["verify_nonce"] = base64.b64encode(nonce).decode("utf-8")
        meta["verify_ciphertext"] = base64.b64encode(verify_ciphertext).decode("utf-8")

        self._save_metadata(meta)
        return True

    def get_status(self) -> Dict[str, Any]:
        meta = self._load_metadata()
        initialized = self.is_initialized()
        protected_list = []
        for rel_path, info in meta.get("protected_files", {}).items():
            norm_rel = rel_path.replace("\\", "/")
            full_p = self.root_dir / norm_rel
            protected_list.append({
                "path": norm_rel,
                "exists": full_p.exists(),
                "masked_at": info.get("masked_at", "Unknown"),
                "size_bytes": info.get("size_bytes", 0)
            })
        return {
            "initialized": initialized,
            "protected_count": len(protected_list),
            "protected_files": protected_list
        }

    def mask_file(self, target_path: Path, password: str) -> str:
        abs_path = target_path.resolve()
        if not abs_path.exists() or not abs_path.is_file():
            raise FileNotFoundError(f"Target file '{target_path}' does not exist or is not a file.")

        if not self.is_initialized():
            self.init_vault(password)
        elif not self.verify_password(password):
            raise ValueError("Invalid master password.")

        try:
            rel_path = str(abs_path.relative_to(self.root_dir)).replace("\\", "/")
        except ValueError:
            rel_path = str(abs_path.name).replace("\\", "/")

        raw_bytes = abs_path.read_bytes()
        if raw_bytes.startswith(MAGIC_HEADER):
            # Already encrypted
            return rel_path

        meta = self._load_metadata()
        salt = base64.b64decode(meta["kdf_salt"])
        key = _derive_key(password, salt)

        file_nonce = os.urandom(12)
        aesgcm = AESGCM(key)
        encrypted_payload = aesgcm.encrypt(file_nonce, raw_bytes, None)

        final_bytes = MAGIC_HEADER + file_nonce + encrypted_payload
        abs_path.write_bytes(final_bytes)

        meta["protected_files"][rel_path] = {
            "masked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "size_bytes": len(raw_bytes)
        }
        self._save_metadata(meta)
        return rel_path

    def unmask_file(self, target_path: Path, password: str) -> str:
        abs_path = target_path.resolve()
        if not abs_path.exists() or not abs_path.is_file():
            raise FileNotFoundError(f"Target file '{target_path}' does not exist.")

        if not self.is_initialized():
            raise ValueError("Vault is not initialized.")
        if not self.verify_password(password):
            raise ValueError("Invalid master password.")

        try:
            rel_path = str(abs_path.relative_to(self.root_dir)).replace("\\", "/")
        except ValueError:
            rel_path = str(abs_path.name).replace("\\", "/")

        raw_bytes = abs_path.read_bytes()
        if not raw_bytes.startswith(MAGIC_HEADER):
            raise ValueError(f"File '{rel_path}' is not encrypted with Archon Secret Vault.")

        meta = self._load_metadata()
        salt = base64.b64decode(meta["kdf_salt"])
        key = _derive_key(password, salt)

        file_nonce = raw_bytes[len(MAGIC_HEADER):len(MAGIC_HEADER) + 12]
        ciphertext = raw_bytes[len(MAGIC_HEADER) + 12:]

        aesgcm = AESGCM(key)
        try:
            plaintext = aesgcm.decrypt(file_nonce, ciphertext, None)
        except Exception:
            raise ValueError(f"Failed to decrypt '{rel_path}'. Invalid password or tampered file.")

        abs_path.write_bytes(plaintext)

        # Remove matching entry from protected_files (checking both norm and raw)
        for key in list(meta["protected_files"].keys()):
            if key.replace("\\", "/") == rel_path or key == rel_path:
                del meta["protected_files"][key]

        self._save_metadata(meta)

        return rel_path

    def change_password(self, old_password: str, new_password: str) -> bool:
        if not self.is_initialized():
            raise ValueError("Vault is not initialized.")
        if not self.verify_password(old_password):
            raise ValueError("Incorrect current master password.")
        if not new_password or not isinstance(new_password, str):
            raise ValueError("New password must be a non-empty string.")

        meta = self._load_metadata()
        old_salt = base64.b64decode(meta["kdf_salt"])
        old_key = _derive_key(old_password, old_salt)
        old_aesgcm = AESGCM(old_key)

        decrypted_cache: Dict[str, bytes] = {}

        # 1. Decrypt all protected files in memory using old key
        for rel_path in list(meta.get("protected_files", {}).keys()):
            full_p = self.root_dir / rel_path
            if full_p.exists() and full_p.is_file():
                file_bytes = full_p.read_bytes()
                if file_bytes.startswith(MAGIC_HEADER):
                    file_nonce = file_bytes[len(MAGIC_HEADER):len(MAGIC_HEADER) + 12]
                    ciphertext = file_bytes[len(MAGIC_HEADER) + 12:]
                    plaintext = old_aesgcm.decrypt(file_nonce, ciphertext, None)
                    decrypted_cache[rel_path] = plaintext

        # 2. Derive new key with fresh salt
        new_salt = os.urandom(16)
        new_verify_nonce = os.urandom(12)
        new_key = _derive_key(new_password, new_salt)
        new_aesgcm = AESGCM(new_key)

        new_verify_ciphertext = new_aesgcm.encrypt(new_verify_nonce, VERIFY_TOKEN, None)

        meta["kdf_salt"] = base64.b64encode(new_salt).decode("utf-8")
        meta["verify_nonce"] = base64.b64encode(new_verify_nonce).decode("utf-8")
        meta["verify_ciphertext"] = base64.b64encode(new_verify_ciphertext).decode("utf-8")

        # 3. Re-encrypt cached files with new key
        for rel_path, plaintext in decrypted_cache.items():
            full_p = self.root_dir / rel_path
            new_file_nonce = os.urandom(12)
            new_ciphertext = new_aesgcm.encrypt(new_file_nonce, plaintext, None)
            full_p.write_bytes(MAGIC_HEADER + new_file_nonce + new_ciphertext)

        self._save_metadata(meta)
        return True
