import os
import sys
from imapclient import IMAPClient

# Manually read .env file (placed in the same directory as the script)
def load_env_file(path='.env'):
    env = {}
    try:
        with open(path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    key, val = line.split('=', 1)
                    val = val.strip().strip('"').strip("'")
                    env[key.strip()] = val
    except FileNotFoundError:
        sys.exit(f"[ERROR] Unable to find {path} file, please confirm its existence in the current directory.")
    return env

# Load environment variables
env = load_env_file('.env')
IMAP_HOST = env.get('IMAP_HOST')
IMAP_USER = env.get('IMAP_USER')
IMAP_PASS = env.get('IMAP_PASS')

if not IMAP_HOST or not IMAP_USER or not IMAP_PASS:
    sys.exit("[ERROR] Please set IMAP_HOST, IMAP_USER, and IMAP_PASS in the .env file")

def clean_old_labels(imap_client):
    # List all remote folder names
    existing_folders = {finfo[2] for finfo in imap_client.list_folders()}
    # Select all folders starting with High or Low, or named Processed
    to_delete = {lbl for lbl in existing_folders
                 if lbl.startswith('High') or lbl.startswith('Low') or lbl == 'Processed'}
    for lbl in to_delete:
        try:
            print(f"[INFO] Deleting old label: {lbl}")
            imap_client.delete_folder(lbl)
        except Exception as e:
            print(f"[WARN] Unable to delete label {lbl}: {e}")

def main():
    print("[INFO] Connecting to IMAP...")
    client = IMAPClient(IMAP_HOST, ssl=True)
    client.login(IMAP_USER, IMAP_PASS)
    client.select_folder("INBOX")
    clean_old_labels(client)
    client.logout()
    print("[INFO] Old labels have been deleted successfully.")

if __name__ == "__main__":
    main()
