from config import OLD_LABELS, LABEL_MAP, PROCESSED_CAT


def clean_labels(imap):
    existing = {f[2] for f in imap.list_folders()}
    for lbl in set(OLD_LABELS)&existing:
        try: imap.delete_folder(lbl)
        except: pass


def ensure_labels(imap):
    existing = {f[2] for f in imap.list_folders()}
    needed = set(LABEL_MAP.values())|{LABEL_MAP[PROCESSED_CAT]}
    for lbl in needed-existing:
        try: imap.create_folder(lbl)
        except: pass