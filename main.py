# main.py
import email
import argparse
import sys
from imapclient import IMAPClient

from config import IMAP_HOST, IMAP_USER, IMAP_PASS, PROCESSED_CAT, LABEL_MAP
from classification_utils import classify_content, fetch_plaintext
from gmail_utils import ensure_labels


def chunk_list(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i+n]


def main():
    parser = argparse.ArgumentParser(description="AI email classifier: process specific UIDs")
    parser.add_argument(
        '--uids',
        help='Comma-separated list of message UIDs to classify',
        required=True
    )
    parser.add_argument(
        '--mark-seen', action='store_true',
        help='Mark processed messages as Seen'
    )
    args = parser.parse_args()

    # Parse UIDs
    try:
        uids = [int(x) for x in args.uids.split(',') if x.strip()]
    except ValueError:
        sys.exit("[ERROR] Invalid --uids format; must be comma-separated integers.")
    if not uids:
        sys.exit("[ERROR] No UIDs provided to process.")

    print(f"[INFO] Processing {len(uids)} messages.")

    # Connect to IMAP
    imap = IMAPClient(IMAP_HOST, ssl=True)
    imap.login(IMAP_USER, IMAP_PASS)
    imap.select_folder('INBOX')
    print("[INFO] IMAP connection established and INBOX selected.")

    # Ensure labels exist
    ensure_labels(imap)
    print("[INFO] Gmail labels checked.")

    # Batch processing
    for batch in chunk_list(uids, 50):
        # Add 'FLAGS' to get system flags at once
        fetch_attrs = ['BODY.PEEK[]', 'X-GM-LABELS', 'FLAGS', 'X-GM-MSGID']

        batch_data = imap.fetch(batch, fetch_attrs)

        for uid in batch:
            data = batch_data.get(uid, {})

            # —— Read flags from FETCH result ——  
            raw_flags = data.get(b'FLAGS', [])  # 可能是 bytes 或 str
            flags = []
            for f in raw_flags:
                flags.append(f.decode() if isinstance(f, bytes) else f)
            seen = '\\Seen' in flags

            # Extract body
            msg_bytes = None
            for key in (b'BODY[]', b'BODY.PEEK[]', b'BODY[PEEK[]]', b'RFC822'):
                if key in data:
                    msg_bytes = data[key]
                    break
            if not msg_bytes:
                print(f"[WARN] UID {uid} has no body, skipped.")
                continue

            msg = email.message_from_bytes(msg_bytes)
            body = fetch_plaintext(msg)
            headers = {
                'From': msg.get('From', ''),
                'To': msg.get('To', ''),
                'Subject': msg.get('Subject', ''),
                'Date': msg.get('Date', '')
            }

            # Call classification
            category = classify_content(body, headers)
            
            # Ensure there is a classification result, if not, default to LowPriority
            if not category or category not in LABEL_MAP:
                category = "LowPriority"
                print(f"[INFO] UID {uid} cannot be classified. Using default LowPriority.")

            # Add labels
            existing = [lbl.decode() if isinstance(lbl, bytes) else lbl
                        for lbl in data.get(b'X-GM-LABELS', [])]
            
            # Ensure both labels exist, one is the category label, one is the Processed label
            labels_to_add = []
            
            # Check category label
            category_label = LABEL_MAP.get(category)
            if category_label and category_label not in existing:
                labels_to_add.append(category_label)
            
            # Check Processed label
            processed_label = LABEL_MAP.get(PROCESSED_CAT)
            if processed_label and processed_label not in existing:
                labels_to_add.append(processed_label)
            
            # Add labels
            if labels_to_add:
                imap.add_gmail_labels(uid, labels_to_add, silent=True)
                print(f"[INFO] UID {uid} labeled: {labels_to_add}")
            else:
                print(f"[INFO] UID {uid} already has required labels. No action taken.")

            # Restore original seen status
            if args.mark_seen:
                imap.add_flags(uid, ['\\Seen'])
                print(f"[INFO] UID {uid} marked as Seen.")
            else:
                if not seen:
                    imap.remove_flags(uid, ['\\Seen'])
                    
                else:
                    print(f"[INFO] UID {uid} was already Seen. No change.")

    # Logout
    try:
        imap.logout()
    except Exception:
        pass
    print("[INFO] IMAP logout complete. main.py finished.")


if __name__ == '__main__':
    main()
