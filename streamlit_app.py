"""
AI経費精算リーダー
領収書・レシートの画像 / PDF を Claude API で読み取り、経費精算CSVに変換する Streamlit アプリ。

起動:
    streamlit run streamlit_app.py
"""
from __future__ import annotations

from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent

# ─────────────────────────────────────────
# ページ設定
# ─────────────────────────────────────────
st.set_page_config(
    page_title="AI経費精算リーダー",
    page_icon="🧾",
    layout="wide",
)

st.title("🧾 AI経費精算リーダー")
st.caption("領収書・レシートの画像 / PDF をAIで読み取り、経費精算CSVに変換します。")

# ─────────────────────────────────────────
# サイドバー（設定）
# ─────────────────────────────────────────
with st.sidebar:
    st.header("設定")
    model = st.selectbox(
        "モデル",
        ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5"],
        index=0,
        help="精度を上げたいときは Opus、速度・コスト優先なら Haiku。",
    )
    csv_format = st.selectbox(
        "CSV形式",
        ["経費精算書", "freee", "マネーフォワード", "弥生"],
        index=0,
    )

# ─────────────────────────────────────────
# アップロード
# ─────────────────────────────────────────
uploaded = st.file_uploader(
    "レシート画像 / PDF をアップロード（複数可）",
    type=["jpg", "jpeg", "png", "pdf"],
    accept_multiple_files=True,
)

if uploaded:
    st.success(f"{len(uploaded)} 件のファイルを受け取りました。")
    st.info("AI読み取り機能は次のステップ（src/extractor.py）で実装します。")
else:
    st.info("レシートの画像またはPDFをアップロードしてください。")
