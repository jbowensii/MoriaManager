"""FTP connection test with auto-decrypted password from config."""

from ftplib import FTP
import sys
from pathlib import Path

# Add the src directory to path so we can import the security module
sys.path.insert(0, str(Path(__file__).parent / "src"))

from moria_manager.config.security import decrypt_password
from configparser import ConfigParser
import os

# Read from myservers.ini
ini_path = Path(os.path.expandvars(r"%APPDATA%\MoriaManager\myservers.ini"))

if not ini_path.exists():
    print(f"Config file not found: {ini_path}")
    sys.exit(1)

config = ConfigParser()
config.read(ini_path, encoding="utf-8")

print("Available servers:")
for i, section in enumerate(config.sections()):
    print(f"  {i+1}. {section}")

section_name = config.sections()[0] if len(config.sections()) == 1 else None
if not section_name:
    choice = input("\nEnter server number: ")
    section_name = config.sections()[int(choice) - 1]

print(f"\nSelected: {section_name}")
print("-" * 50)

# Get connection details
host = config.get(section_name, "host", fallback="")
port = int(config.get(section_name, "port", fallback="21"))
username = config.get(section_name, "username", fallback="")
encrypted_password = config.get(section_name, "password", fallback="")

# Decrypt password
password = decrypt_password(encrypted_password)

print(f"Host: {host}")
print(f"Port: {port}")
print(f"Username: {username}")
print(f"Password: {'*' * len(password)} ({len(password)} chars)")
print("-" * 50)

try:
    print("\n1. Connecting to FTP server...")
    ftp = FTP()
    ftp.connect(host, port, timeout=10)

    print("2. Logging in...")
    ftp.login(username, password)

    print("\n SUCCESS! Connected to FTP server!")
    print("-" * 50)

    # Get current directory
    print(f"\nCurrent directory: {ftp.pwd()}")

    # List directory
    print("\nDirectory listing:")
    try:
        files = ftp.nlst()
        for f in files[:15]:
            print(f"  {f}")
        if len(files) > 15:
            print(f"  ... and {len(files) - 15} more items")
    except Exception as e:
        print(f"  Could not list directory: {e}")

    # Clean up
    ftp.quit()
    print("\nConnection closed successfully.")

except Exception as e:
    print(f"\n CONNECTION ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
