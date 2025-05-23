import subprocess
import sys
import time
import argparse
import email
import sqlite3
from datetime import datetime, timezone
import base64
from email import policy
from email.parser import BytesParser

from config import (
    CATEGORY_PREFIX, EXCLUDED_CATEGORIES, IMAP_HOST, IMAP_USER, IMAP_PASS,
    PROCESSED_CAT, REPORT_ENABLED, REPORT_TO,
    LABEL_MAP, MAIN_CATS
)
from imapclient import IMAPClient
from ollama_utils import start_ollama, kill_ollama
from gmailauth import get_service

CREATE_NO_WINDOW = 0x08000000

CHECK_INTERVAL = 180
DB_PATH = 'processed_emails.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='processed'")
    if not c.fetchone():
        c.execute('''
            CREATE TABLE processed (
                uid INTEGER PRIMARY KEY,
                processed_at TEXT,
                sent INTEGER DEFAULT 0,
                was_unread INTEGER,
                category TEXT
            )
        ''')
    else:
        c.execute("PRAGMA table_info(processed)")
        columns = [col[1] for col in c.fetchall()]
        if 'category' not in columns:
            c.execute("ALTER TABLE processed ADD COLUMN category TEXT")
    conn.commit()
    conn.close()

def find_gmail_message_id(service, subject, from_addr, date=None):
    import time
    queries = []
    # 主组合：subject + from
    if subject and from_addr:
        queries.append(f'subject:"{subject}" from:"{from_addr}"')
    if subject:
        queries.append(f'subject:"{subject}"')
    if from_addr:
        queries.append(f'from:"{from_addr}"')
    # 时间范围
    if date:
        day = time.strftime('%Y/%m/%d', time.gmtime(date))
        if subject and from_addr:
            queries.append(f'subject:"{subject}" from:"{from_addr}" after:{day}')
        if subject:
            queries.append(f'subject:"{subject}" after:{day}')
        if from_addr:
            queries.append(f'from:"{from_addr}" after:{day}')
    # 依次尝试所有组合
    for query in queries:
        print(f"[DEBUG] Gmail API search query: {query}")
        result = service.users().messages().list(userId='me', q=query).execute()
        msgs = result.get('messages', [])
        if msgs:
            return msgs[0]['id']
    return None

def send_individual_report(uid, imap, gmail_service, assigned):
    from email.utils import parseaddr, formataddr
    from config import CATEGORY_PREFIX

    data = imap.fetch([uid], ['RFC822'])[uid]
    raw_bytes = data[b'RFC822']
    orig = BytesParser(policy=policy.default).parsebytes(raw_bytes)

    subject    = orig.get('Subject', '')
    from_addr  = orig.get('From', '')
    date_tuple = email.utils.parsedate_tz(orig.get('Date'))
    timestamp  = email.utils.mktime_tz(date_tuple) if date_tuple else None

    gmail_id = find_gmail_message_id(gmail_service, subject, from_addr, date=timestamp)
    if not gmail_id:
        print(f"[ERROR] 找不到 Gmail messageId uid={uid}, subject={subject}")
        return

    # 只走 raw send，自定义前缀
    print(f"[INFO] Using raw send (custom prefix)")
    resp      = gmail_service.users().messages().get(
                    userId='me', id=gmail_id, format='raw'
                ).execute()
    raw_gmail = base64.urlsafe_b64decode(resp['raw'])

    msg = BytesParser(policy=policy.default).parsebytes(raw_gmail)
    msg.replace_header('To', REPORT_TO)
    prefix = CATEGORY_PREFIX.get(assigned, "【其他】")
    msg.replace_header('Subject', prefix + subject)

    orig_name, _ = parseaddr(from_addr)
    msg.replace_header('From', formataddr((orig_name, IMAP_USER)))

    if msg.get('Reply-To'):
        msg.replace_header('Reply-To', from_addr)
    else:
        msg['Reply-To'] = from_addr

    new_raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
    gmail_service.users().messages().send(
        userId='me',
        body={'raw': new_raw}
    ).execute()
    print(f"[INFO] Raw send succeeded uid={uid} → {REPORT_TO}")

    imap.add_gmail_labels(uid, [PROCESSED_CAT], silent=True)



def record_and_send(uids, unread_uids, imap, gmail_service):
    if not uids:
        return
    for uid in uids:
        # 1) Get the original content, check who the sender is
        data = imap.fetch([uid], ['RFC822', 'X-GM-LABELS'])[uid]
        orig = email.message_from_bytes(data[b'RFC822'])
        from_addr = orig.get('From', '')
        if REPORT_TO.lower() in from_addr.lower():
            print(f"[INFO] UID {uid} 来自 {REPORT_TO}，跳过转发")
            continue
        # 拉标签判断
        data = imap.fetch([uid], ['X-GM-LABELS'])
        labels = [l.decode() if isinstance(l, bytes) else l for l in data[uid].get(b'X-GM-LABELS', [])]
        cats = set(LABEL_MAP.values())
        assigned = next((lbl for lbl in labels if lbl in cats), None)
        print(f"[DEBUG] UID {uid} labels: {labels}")
        print(f"[DEBUG] LABEL_MAP.values(): {cats}")
        print(f"[DEBUG] assigned = {assigned}")
        print(f"[DEBUG] EXCLUDED_CATEGORIES = {EXCLUDED_CATEGORIES}")
        if assigned not in EXCLUDED_CATEGORIES:
            print("[DEBUG] Matched criteria, preparing to forward/report email.")
            send_individual_report(uid, imap, gmail_service, assigned)
        else:
            print(f"[INFO] UID {uid} 属于 {assigned}，不转发")

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

def get_unprocessed_uids(imap, limit_to_unseen=False):
    target_uids = imap.search(['UNSEEN']) if limit_to_unseen else imap.search(['ALL'])
    if not target_uids:
        print("[INFO] 没有邮件需要检查")
        return []
    unproc = []
    for batch in chunk_list(target_uids, 100):
        data = imap.fetch(batch, ['X-GM-LABELS'])
        for uid, d in data.items():
            labels = [l.decode() if isinstance(l, bytes) else l for l in d.get(b'X-GM-LABELS', [])]
            if PROCESSED_CAT not in labels:
                unproc.append(uid)
    label = "Unread and unprocessed" if limit_to_unseen else "All unprocessed"
    print(f"[INFO] Detected {len(unproc)} unread and unprocessed emails.")
    return unproc

def run_main_process(uids, imap, mark_seen, gmail_service):
    if not uids:
        return
    for batch in chunk_list(uids, 30):
        uids_arg = ','.join(map(str, batch))
        CREATE_NO_WINDOW = 0x08000000
        print(f"[INFO] Running classification script for {len(batch)} emails (UIDs: {batch[0]}-{batch[-1]})")
        ret = subprocess.call([sys.executable, 'main.py', '--uids', uids_arg], creationflags=CREATE_NO_WINDOW)
        print(f"[INFO] main.py returned {ret}")
        record_and_send(batch, batch if mark_seen else [], imap, gmail_service)
        if mark_seen:
            for uid in batch:
                try:
                    imap.add_flags(uid, ['\\Seen'])
                    print(f"[INFO] UID {uid} marked as Seen.")
                except:
                    pass

def launcher(include_history=False):
    init_db()
    gmail_service = get_service()
    imap = IMAPClient(IMAP_HOST, ssl=True)
    imap.login(IMAP_USER, IMAP_PASS)
    imap.select_folder('INBOX')
    print(f"[INFO] IMAP connection established: {IMAP_HOST}")
    try:
        if include_history:
            print("[INFO] 开始回溯未处理邮件，优先处理未读...")
            while True:
                to_unread = get_unprocessed_uids(imap, limit_to_unseen=True)
                if to_unread:
                    print(f"[INFO] 处理未读未处理：{len(to_unread)} 封")
                    start_ollama()
                    run_main_process(to_unread[:30], imap, mark_seen=True, gmail_service=gmail_service)
                    kill_ollama()
                    time.sleep(0.5)
                    continue
                history = get_unprocessed_uids(imap, limit_to_unseen=False)
                if not history:
                    print("[INFO] All emails have been processed")
                    break
                print(f"[INFO] Processing {len(history[:30])} historical read but unprocessed emails")
                start_ollama()
                run_main_process(history[:30], imap, mark_seen=False, gmail_service=gmail_service)
                kill_ollama()
                time.sleep(0.5)
        while True:
            print(f"[INFO] Starting new round: launching model and occupying VRAM.")
            start_ollama()  # 每轮前启动
            to_unread = get_unprocessed_uids(imap, limit_to_unseen=True)
            if to_unread:
                run_main_process(to_unread, imap, mark_seen=True, gmail_service=gmail_service)
            else:
                history = get_unprocessed_uids(imap, limit_to_unseen=False)
                if history:
                    run_main_process(history[:30], imap, mark_seen=False, gmail_service=gmail_service)
                else:
                    print("[INFO] 本轮无邮件需处理")
            print(f"[INFO] Ollama processes killed.")
            kill_ollama()   # 每轮后关闭，释放 VRAM
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("[INFO] 收到退出信号，退出中...")
    finally:
        try:
            imap.logout()
        except:
            pass
        kill_ollama()
        print("[INFO] Launcher exited, model unloaded.")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="AI 邮件分类器 Launcher")
    parser.add_argument('--uid', type=int, help='处理指定UID后退出')
    parser.add_argument('--include-history', action='store_true', help='回溯并处理所有未处理邮件（优先处理未读）')
    args = parser.parse_args()
    gmail_service = get_service()
    if args.uid:
        init_db()
        start_ollama()
        imap = IMAPClient(IMAP_HOST, ssl=True)
        imap.login(IMAP_USER, IMAP_PASS)
        imap.select_folder('INBOX')
        run_main_process([args.uid], imap, mark_seen=True, gmail_service=gmail_service)
        imap.logout()
        kill_ollama()
    else:
        launcher(include_history=args.include_history)
