# gmailauth.py

import os
import pickle
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

# 你原来定义的 SCOPES 列表
SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/gmail.compose',
]

def get_service():
    creds = None
    # 1) 载入本地 token.pickle（如果存在）
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as f:
            creds = pickle.load(f)

    # 2) 如果没有或已经失效，就重新走 OAuth 流程
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES
            )
            creds = flow.run_local_server(port=0)
        # 保存新 token
        with open('token.pickle', 'wb') as f:
            pickle.dump(creds, f)

    # 3) 构造 Gmail API client，强制不走旧缓存
    service = build(
        'gmail', 'v1',
        credentials=creds,
        cache_discovery=False,
        static_discovery=False
    )

    return service
