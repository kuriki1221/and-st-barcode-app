"""
Googleドライブへのラベルzip自動アップロード

サービスアカウントの認証情報は Streamlit の secrets 機能
(st.secrets["gcp_service_account"]) から読み込む。
鍵ファイル自体はリポジトリに含めない。
"""
import io

import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def is_configured():
    try:
        return "gcp_service_account" in st.secrets
    except Exception:
        return False


def upload_zip(file_bytes, filename, folder_id):
    """
    file_bytes: zipファイルのバイナリ
    filename: ドライブ上のファイル名
    folder_id: アップロード先フォルダのID
    戻り値: アップロードしたファイルのwebViewLink
    """
    info = dict(st.secrets["gcp_service_account"])
    credentials = service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    service = build("drive", "v3", credentials=credentials)

    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype="application/zip", resumable=False)
    metadata = {"name": filename, "parents": [folder_id]}
    file = (
        service.files()
        .create(body=metadata, media_body=media, fields="id, webViewLink", supportsAllDrives=True)
        .execute()
    )
    return file.get("webViewLink")
