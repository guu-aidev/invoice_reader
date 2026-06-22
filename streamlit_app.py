"""
AI経費精算リーダー
領収書・レシートの画像 / PDF を Claude API で読み取り、経費精算CSVに変換する Streamlit アプリ。

起動:
    streamlit run streamlit_app.py
"""
from __future__ import annotations

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from src import csv_writer
from src.accounts import DEFAULT_ACCOUNTS
from src.extractor import DEFAULT_MODEL, Receipt, extract_receipt, verify_totals

load_dotenv()

# ─────────────────────────────────────────
# ページ設定
# ─────────────────────────────────────────
st.set_page_config(page_title="AI経費精算リーダー", page_icon="🧾", layout="wide")

# 全体の文字を少し大きめに（既定 16px → 18px 相当）
st.markdown(
    """
    <style>
      html, body, [class*="st-"], .stMarkdown, .stDataFrame { font-size: 1.12rem; }
      [data-testid="stSidebar"] * { font-size: 1.08rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🧾 AI経費精算リーダー")
st.caption("領収書・レシートの画像 / PDF をAIで読み取り、経費精算CSVに変換します。")

# セッション状態（再描画でAPIを呼び直さないように保持）
st.session_state.setdefault("receipts", [])
st.session_state.setdefault("filenames", [])

# ─────────────────────────────────────────
# サイドバー（設定）
# ─────────────────────────────────────────
with st.sidebar:
    st.header("設定")
    model = st.selectbox(
        "モデル (Claude)",
        ["claude-sonnet-4-6", "claude-opus-4-8", "claude-haiku-4-5"],
        index=0,
        format_func=lambda m: m.removeprefix("claude-"),
        help="精度を上げたいときは Opus、速度・コスト優先なら Haiku。",
    )
    output_format = st.selectbox(
        "出力形式",
        ["経費精算書", "会計仕訳（汎用）"],
        index=0,
        help="経費精算書＝会社へ提出用 / 会計仕訳＝会計ソフト取込用（税率別）。"
        "freee・マネーフォワード・弥生などの専用形式にも拡張できる設計にしています。",
    )

# ─────────────────────────────────────────
# 1. アップロード → 読み取り
# ─────────────────────────────────────────
uploaded = st.file_uploader(
    "レシート画像 / PDF をアップロード（複数可）",
    type=["jpg", "jpeg", "png", "pdf"],
    accept_multiple_files=True,
)

if uploaded:
    if st.button(f"📷 {len(uploaded)} 件を読み取る", type="primary"):
        receipts: list[Receipt] = []
        filenames: list[str] = []
        progress = st.progress(0.0, text="読み取り中 ...")
        for i, f in enumerate(uploaded):
            try:
                r = extract_receipt(f.getvalue(), f.name, model=model)
                receipts.append(r)
                filenames.append(f.name)
            except Exception as e:  # 1枚失敗しても他は続ける
                st.error(f"{f.name}: 読み取りに失敗しました（{e}）")
            progress.progress((i + 1) / len(uploaded), text=f"{i + 1} / {len(uploaded)} 完了")
        progress.empty()
        st.session_state.receipts = receipts
        st.session_state.filenames = filenames
        if receipts:
            st.success(f"{len(receipts)} 件を読み取りました。下の表で確認・修正できます。")

# ─────────────────────────────────────────
# 2. 結果テーブル（編集可） → 3. CSVダウンロード
# ─────────────────────────────────────────
receipts: list[Receipt] = st.session_state.receipts
filenames: list[str] = st.session_state.filenames

if receipts:
    # 編集用のテーブルを組み立て（状態列で要確認を一目で分かるように）
    rows = []
    review_count = 0
    for fname, r in zip(filenames, receipts):
        ok, msg = verify_totals(r)
        needs_review = (not ok) or bool(r.confidence_notes)
        if needs_review:
            review_count += 1
        detail = "" if ok else msg
        if r.confidence_notes:
            detail = f"{detail} / {r.confidence_notes}" if detail else r.confidence_notes
        rows.append(
            {
                "状態": "⚠️" if needs_review else "✅",
                "ファイル": fname,
                "日付": r.used_date,
                "支払先": r.vendor_name,
                "登録番号": r.registration_number or "",
                "税込合計": r.total_amount,
                "消費税": sum(t.tax_amount for t in r.tax_lines),
                "勘定科目": r.suggested_account,
                "摘要": r.description,
                "支払方法": r.payment_method or "",
                "要確認": detail or "OK",
            }
        )
    df = pd.DataFrame(rows)

    # 勘定科目ドロップダウンの選択肢（AIの提案が候補外でも選べるよう合わせる）
    account_options = list(dict.fromkeys(DEFAULT_ACCOUNTS + [r.suggested_account for r in receipts]))

    # サマリ（要確認の件数を上部に表示）
    if review_count:
        st.warning(
            f"⚠️ {review_count} 件が要確認です（金額不一致 または 読み取りが不確かな行）。"
            "確認・修正してからダウンロードしてください。"
        )
    else:
        st.success("✅ 全件 読み取りOK")

    st.subheader("読み取り結果（セルを直接編集できます）")
    st.caption("「状態」列の見出しをクリックすると ⚠️ を上にまとめられます。")
    edited = st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["状態", "ファイル", "消費税", "要確認"],  # これらは編集不可
        column_config={
            "状態": st.column_config.TextColumn("状態", width="small", help="⚠️=要確認 / ✅=OK"),
            "勘定科目": st.column_config.SelectboxColumn("勘定科目", options=account_options, required=True),
            "税込合計": st.column_config.NumberColumn("税込合計", format="%d", min_value=0),
            "登録番号": st.column_config.TextColumn("登録番号", help="適格請求書発行事業者の登録番号 T+13桁"),
        },
    )

    # 編集内容を Receipt に反映（税率内訳は抽出結果のまま使用）
    for i, r in enumerate(receipts):
        row = edited.iloc[i]
        r.used_date = str(row["日付"])
        r.vendor_name = str(row["支払先"])
        r.registration_number = str(row["登録番号"]) or None
        r.total_amount = int(row["税込合計"])
        r.suggested_account = str(row["勘定科目"])
        r.description = str(row["摘要"])
        r.payment_method = str(row["支払方法"]) or None

    # CSVダウンロード（サイドバーで選んだ出力形式で1ファイル出力）
    st.subheader("CSVダウンロード")
    if output_format == "経費精算書":
        out_df = csv_writer.expense_report_df(receipts)
        out_name = "経費精算書.csv"
    else:  # 会計仕訳（汎用）
        out_df = csv_writer.accounting_df(receipts)
        out_name = "会計仕訳.csv"
    st.download_button(
        "⬇ CSVをダウンロード",
        data=csv_writer.df_to_csv_bytes(out_df),
        file_name=out_name,
        mime="text/csv",
        type="primary",
        use_container_width=True,
    )
    st.caption(f"出力形式: 「{output_format}」（サイドバーで変更できます）")
else:
    st.info("レシートの画像またはPDFをアップロードして「読み取る」を押してください。")
