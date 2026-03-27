"""
licensing/client.py

Client-side licensing module for NSP Plugin.
Handles license activation, validation, and heartbeats.
"""
import hashlib
import json
import platform
import socket
import subprocess
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict

import requests
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LicenseError(Exception):
    """License validation error."""
    pass


class LicenseClient:
    """Client for NSP Plugin licensing system."""

    def __init__(
        self,
        license_server: str = "https://license.vilearn.ai",
        cache_dir: Optional[Path] = None
    ):
        self.license_server = license_server.rstrip("/")
        self.cache_dir = cache_dir or (Path.home() / ".nsp" / "license")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.token_file = self.cache_dir / "token.json"
        self.machine_id = self._generate_machine_id()

    def _generate_machine_id(self) -> str:
        """
        Generate unique machine ID based on hardware fingerprint.

        Uses:
        - MAC address (primary network interface)
        - CPU serial (macOS) or machine GUID (Windows)
        - Disk UUID (boot volume)
        - Hostname

        Returns immutable 32-character hex string.
        """
        components = []

        # MAC address
        try:
            mac = hex(uuid.getnode())[2:]
            components.append(mac)
        except Exception as e:
            logger.warning(f"Failed to get MAC address: {e}")
            components.append("no-mac")

        # Platform-specific identifiers
        system = platform.system()

        if system == "Darwin":  # macOS
            try:
                # Get IOPlatformSerialNumber
                result = subprocess.run(
                    ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.split("\n"):
                    if "IOPlatformSerialNumber" in line:
                        serial = line.split('"')[3]
                        components.append(serial)
                        break
            except Exception as e:
                logger.warning(f"Failed to get CPU serial: {e}")

            # Disk UUID
            try:
                result = subprocess.run(
                    ["diskutil", "info", "/"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                for line in result.stdout.split("\n"):
                    if "Volume UUID" in line:
                        disk_uuid = line.split()[-1]
                        components.append(disk_uuid)
                        break
            except Exception as e:
                logger.warning(f"Failed to get disk UUID: {e}")

        elif system == "Windows":
            try:
                # Get Windows machine GUID
                result = subprocess.run(
                    ["wmic", "csproduct", "get", "UUID"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                guid = result.stdout.split("\n")[1].strip()
                components.append(guid)
            except Exception as e:
                logger.warning(f"Failed to get machine GUID: {e}")

        # Hostname
        try:
            hostname = socket.gethostname()
            components.append(hostname)
        except Exception as e:
            logger.warning(f"Failed to get hostname: {e}")

        # Combine and hash
        fingerprint = "|".join(sorted(filter(None, components)))
        machine_id = hashlib.sha256(fingerprint.encode()).hexdigest()

        return machine_id[:32]

    def _save_token(self, token_data: dict):
        """Save token to cache file."""
        self.token_file.write_text(json.dumps(token_data, indent=2))
        logger.info(f"Token saved to {self.token_file}")

    def _load_token(self) -> Optional[dict]:
        """Load token from cache file."""
        if not self.token_file.exists():
            return None

        try:
            return json.loads(self.token_file.read_text())
        except Exception as e:
            logger.error(f"Failed to load token: {e}")
            return None

    def _is_token_expired(self, token_data: dict) -> bool:
        """Check if token is expired (needs heartbeat)."""
        saved_at = datetime.fromisoformat(token_data.get("saved_at", "2000-01-01"))
        age = datetime.utcnow() - saved_at

        return age > timedelta(hours=24)

    def activate(self, license_key: str, machine_name: Optional[str] = None) -> dict:
        """
        Activate license on this machine.

        Args:
            license_key: License key (e.g., "VELA-XXXX-XXXX-XXXX-XXXX")
            machine_name: Optional friendly name for this machine

        Returns:
            Activation response with token and features

        Raises:
            LicenseError: If activation fails
        """
        if not machine_name:
            machine_name = platform.node()

        payload = {
            "license_key": license_key,
            "machine_id": self.machine_id,
            "machine_name": machine_name,
        }

        try:
            response = requests.post(
                f"{self.license_server}/api/v1/licenses/activate",
                json=payload,
                timeout=10
            )

            if response.status_code != 200:
                error_detail = response.json().get("detail", "Unknown error")
                raise LicenseError(f"Activation failed: {error_detail}")

            data = response.json()

            # Save token
            token_data = {
                "token": data["token"],
                "plan": data["plan"],
                "features": data["features"],
                "expires_at": data.get("expires_at"),
                "saved_at": datetime.utcnow().isoformat(),
            }

            self._save_token(token_data)

            logger.info(f"License activated successfully (plan: {data['plan']})")

            return data

        except requests.RequestException as e:
            raise LicenseError(f"Network error during activation: {e}")

    def validate(self, force_online: bool = False) -> dict:
        """
        Validate current license.

        Args:
            force_online: Force online validation even if local token valid

        Returns:
            Validation result with plan and features

        Raises:
            LicenseError: If validation fails
        """
        token_data = self._load_token()

        if not token_data:
            raise LicenseError("No active license found. Please activate first.")

        # Local validation (offline mode)
        if not force_online and not self._is_token_expired(token_data):
            logger.info("License valid (offline validation)")
            return {
                "valid": True,
                "plan": token_data["plan"],
                "features": token_data["features"],
                "offline": True,
            }

        # Online validation
        try:
            response = requests.post(
                f"{self.license_server}/api/v1/licenses/validate",
                json={"token": token_data["token"]},
                timeout=10
            )

            if response.status_code != 200:
                error_detail = response.json().get("detail", "Unknown error")
                raise LicenseError(f"Validation failed: {error_detail}")

            data = response.json()

            # Update cached token
            token_data["saved_at"] = datetime.utcnow().isoformat()
            self._save_token(token_data)

            logger.info("License valid (online validation)")

            return {
                "valid": data["valid"],
                "plan": data["plan"],
                "features": token_data["features"],
                "offline": False,
                "days_remaining": data.get("days_remaining"),
            }

        except requests.RequestException as e:
            # Offline fallback
            logger.warning(f"Online validation failed: {e}. Using offline mode.")

            if self._is_token_expired(token_data):
                # Token too old, require online validation
                raise LicenseError("License validation required. Please connect to the internet.")

            return {
                "valid": True,
                "plan": token_data["plan"],
                "features": token_data["features"],
                "offline": True,
            }

    def heartbeat(self, plugin_version: str = "2.0.0"):
        """
        Send heartbeat to license server.
        Should be called every 24h to keep token fresh.
        """
        token_data = self._load_token()

        if not token_data:
            logger.warning("No token found for heartbeat")
            return

        try:
            response = requests.post(
                f"{self.license_server}/api/v1/licenses/heartbeat",
                json={
                    "token": token_data["token"],
                    "plugin_version": plugin_version,
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                # Update token
                token_data["token"] = data["token"]
                token_data["saved_at"] = datetime.utcnow().isoformat()
                self._save_token(token_data)

                logger.info("Heartbeat successful")
            else:
                logger.error(f"Heartbeat failed: {response.status_code}")

        except requests.RequestException as e:
            logger.warning(f"Heartbeat failed (network error): {e}")

    def deactivate(self):
        """Deactivate license on this machine."""
        token_data = self._load_token()

        if not token_data:
            raise LicenseError("No active license to deactivate")

        try:
            response = requests.post(
                f"{self.license_server}/api/v1/licenses/deactivate",
                json={"token": token_data["token"]},
                timeout=10
            )

            if response.status_code == 200:
                # Remove cached token
                self.token_file.unlink(missing_ok=True)
                logger.info("License deactivated successfully")
            else:
                error_detail = response.json().get("detail", "Unknown error")
                raise LicenseError(f"Deactivation failed: {error_detail}")

        except requests.RequestException as e:
            raise LicenseError(f"Network error during deactivation: {e}")

    def get_machine_id(self) -> str:
        """Get this machine's unique ID."""
        return self.machine_id

    def get_cached_plan(self) -> Optional[str]:
        """Get plan from cached token (offline)."""
        token_data = self._load_token()
        return token_data.get("plan") if token_data else None

    def get_cached_features(self) -> Optional[dict]:
        """Get features from cached token (offline)."""
        token_data = self._load_token()
        return token_data.get("features") if token_data else None


# ============================================================================
# MODEL ENCRYPTION UTILITIES
# ============================================================================

def derive_model_key(license_key: str, salt: bytes = b"nsp_model_salt_v1") -> bytes:
    """
    Derive encryption key from license key.

    Args:
        license_key: User's license key
        salt: Salt for key derivation (constant)

    Returns:
        32-byte encryption key
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )

    key = base64.urlsafe_b64encode(kdf.derive(license_key.encode()))
    return key


def encrypt_model(model_path: Path, license_key: str, output_path: Optional[Path] = None):
    """
    Encrypt model file with license-derived key.

    Args:
        model_path: Path to original model file
        license_key: License key to derive encryption key
        output_path: Output path (defaults to model_path.with_suffix(".enc"))
    """
    if not output_path:
        output_path = model_path.with_suffix(model_path.suffix + ".enc")

    # Derive key
    key = derive_model_key(license_key)
    fernet = Fernet(key)

    # Encrypt
    plaintext = model_path.read_bytes()
    encrypted = fernet.encrypt(plaintext)

    # Write
    output_path.write_bytes(encrypted)

    logger.info(f"Encrypted {model_path} → {output_path}")


def decrypt_model(encrypted_path: Path, license_key: str) -> bytes:
    """
    Decrypt model file with license-derived key.

    Args:
        encrypted_path: Path to encrypted model
        license_key: License key to derive decryption key

    Returns:
        Decrypted model bytes (in memory)

    Raises:
        LicenseError: If decryption fails (wrong key)
    """
    # Derive key
    key = derive_model_key(license_key)
    fernet = Fernet(key)

    # Decrypt
    encrypted = encrypted_path.read_bytes()

    try:
        decrypted = fernet.decrypt(encrypted)
        return decrypted
    except Exception:
        raise LicenseError("Failed to decrypt model. Invalid license key.")


# ============================================================================
# CLI TOOL
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="NSP Plugin License Client")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Activate command
    activate_parser = subparsers.add_parser("activate", help="Activate license")
    activate_parser.add_argument("license_key", help="License key")
    activate_parser.add_argument("--server", default="http://localhost:8080", help="License server URL")

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate license")
    validate_parser.add_argument("--server", default="http://localhost:8080", help="License server URL")

    # Heartbeat command
    heartbeat_parser = subparsers.add_parser("heartbeat", help="Send heartbeat")
    heartbeat_parser.add_argument("--server", default="http://localhost:8080", help="License server URL")

    # Deactivate command
    deactivate_parser = subparsers.add_parser("deactivate", help="Deactivate license")
    deactivate_parser.add_argument("--server", default="http://localhost:8080", help="License server URL")

    # Machine ID command
    machine_id_parser = subparsers.add_parser("machine-id", help="Show machine ID")

    args = parser.parse_args()

    if args.command == "activate":
        client = LicenseClient(license_server=args.server)
        try:
            result = client.activate(args.license_key)
            print(f"✅ License activated successfully!")
            print(f"Plan: {result['plan']}")
            print(f"Features: {json.dumps(result['features'], indent=2)}")
        except LicenseError as e:
            print(f"❌ Activation failed: {e}")

    elif args.command == "validate":
        client = LicenseClient(license_server=args.server)
        try:
            result = client.validate()
            print(f"✅ License valid!")
            print(f"Plan: {result['plan']}")
            print(f"Offline mode: {result.get('offline', False)}")
            if result.get('days_remaining'):
                print(f"Days remaining: {result['days_remaining']}")
        except LicenseError as e:
            print(f"❌ Validation failed: {e}")

    elif args.command == "heartbeat":
        client = LicenseClient(license_server=args.server)
        client.heartbeat()
        print("✅ Heartbeat sent")

    elif args.command == "deactivate":
        client = LicenseClient(license_server=args.server)
        try:
            client.deactivate()
            print("✅ License deactivated")
        except LicenseError as e:
            print(f"❌ Deactivation failed: {e}")

    elif args.command == "machine-id":
        client = LicenseClient()
        print(f"Machine ID: {client.get_machine_id()}")

    else:
        parser.print_help()
