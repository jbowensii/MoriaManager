"""Simple SFTP connection test script."""

import paramiko
import sys

# Connection details from myservers.ini
HOST = "node.battlematvtt.com"
PORT = 2022
USERNAME = "dungeonmaster.5446bec5"

# You'll need to enter the password manually for this test
PASSWORD = input("Enter password: ")

print(f"\nAttempting to connect to {HOST}:{PORT}")
print(f"Username: {USERNAME}")
print("-" * 50)

try:
    # Create transport
    print("Creating transport...")
    transport = paramiko.Transport((HOST, PORT))

    print("Connecting with credentials...")
    transport.connect(username=USERNAME, password=PASSWORD)

    print("Creating SFTP client...")
    sftp = paramiko.SFTPClient.from_transport(transport)

    print("\n SUCCESS! Connected to SFTP server!")
    print("-" * 50)

    # Try to list the root directory
    print("\nListing root directory:")
    try:
        files = sftp.listdir(".")
        for f in files[:10]:  # Show first 10 files
            print(f"  {f}")
        if len(files) > 10:
            print(f"  ... and {len(files) - 10} more files")
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

except Exception as e:
    print(f"\n CONNECTION ERROR: {type(e).__name__}: {e}")

input("\nPress Enter to exit...")
