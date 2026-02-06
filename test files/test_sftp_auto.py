"""SFTP connection test with auto-decrypted password from config."""

import paramiko
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

# Get connection details - use new host/port fields
host = config.get(section_name, "host", fallback="")
port = config.get(section_name, "port", fallback="22")
username = config.get(section_name, "username", fallback="")
encrypted_password = config.get(section_name, "password", fallback="")

# Decrypt password
password = decrypt_password(encrypted_password)

print(f"Host: {host}")
print(f"Port: {port}")
print(f"Username: {username}")
print(f"Password: {'*' * len(password)} ({len(password)} chars)")
print("-" * 50)

# Check port - warn if it's FTP port
if port == "21":
    print("\n WARNING: Port 21 is FTP, not SFTP!")
    print("SFTP typically uses port 22 (SSH).")
    print("If this is an FTP server, you'll need FTP library instead of paramiko.")
    print("-" * 50)

try:
    # Create transport
    print("\n1. Creating transport...")
    transport = paramiko.Transport((host, int(port)))

    print("2. Connecting with credentials...")
    transport.connect(username=username, password=password)

    print("3. Creating SFTP client...")
    sftp = paramiko.SFTPClient.from_transport(transport)

    print("\n SUCCESS! Connected to SFTP server!")
    print("-" * 50)

    # Try to list the root directory
    print("\nListing current directory:")
    try:
        files = sftp.listdir(".")
        for f in files[:15]:  # Show first 15 files
            try:
                stat = sftp.stat(f)
                is_dir = stat.st_mode & 0o40000
                print(f"  {'[DIR] ' if is_dir else '      '}{f}")
            except:
                print(f"  {f}")
        if len(files) > 15:
            print(f"  ... and {len(files) - 15} more items")
    except Exception as e:
        print(f"  Could not list directory: {e}")

    # Clean up
    sftp.close()
    transport.close()
    print("\nConnection closed successfully.")

except paramiko.AuthenticationException as e:
    print(f"\n AUTHENTICATION FAILED: {e}")
    print("Check username and password.")

except paramiko.SSHException as e:
    print(f"\n SSH ERROR: {e}")
    if "21" in str(port):
        print("\nThis might be because port 21 is FTP, not SFTP.")
        print("Try using an FTP client or check if there's an SFTP port.")

except Exception as e:
    print(f"\n CONNECTION ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
