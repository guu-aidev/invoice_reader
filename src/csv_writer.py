"""抽出した Receipt のリストを CSV にする。

2種類:
- 経費精算書（社内提出用）  : 1レシート＝1行
- 会計仕訳（汎用）          : 税率ごとに1行（軽減税率8%混在に対応）

文字コードは Excel・主要クラウド会計（freee / マネーフォワード等）互換の UTF-8(BOM) 固定。
※ freee / マネーフォワード / 弥生 の各取込フォーマットへの厳密対応は後続で追加予定。
"""
from __future__ import annotations

import pandas as pd

from .extractor import Receipt


def expense_report_df(receipts: list[Receipt]) -> pd.DataFrame:
    """経費精算書（社内提出用）。1レシート＝1行。"""
    rows = []
    for r in receipts:
        consumption_tax = sum(t.tax_amount for t in r.tax_lines)
        rows.append(
            {
                "日付": r.used_date,
                "支払先": r.vendor_name,
                "登録番号": r.registration_number or "",
                "勘定科目": r.suggested_account,
                "税込金額": r.total_amount,
                "消費税": consumption_tax,
                "摘要": r.description,
                "支払方法": r.payment_method or "",
            }
        )
    return pd.DataFrame(rows)


def accounting_df(receipts: list[Receipt]) -> pd.DataFrame:
    """会計仕訳（汎用）。税率ごとに1行。"""
    rows = []
    for r in receipts:
        if r.tax_lines:
            for t in r.tax_lines:
                rows.append(
                    {
                        "日付": r.used_date,
                        "借方勘定科目": r.suggested_account,
                        "借方金額": t.taxable_amount + t.tax_amount,
                        "税区分": f"課税仕入 {t.rate}%",
                        "取引先": r.vendor_name,
                        "登録番号": r.registration_number or "",
                        "摘要": r.description,
                    }
                )
        else:
            rows.append(
                {
                    "日付": r.used_date,
                    "借方勘定科目": r.suggested_account,
                    "借方金額": r.total_amount,
                    "税区分": "",
                    "取引先": r.vendor_name,
                    "登録番号": r.registration_number or "",
                    "摘要": r.description,
                }
            )
    return pd.DataFrame(rows)


def df_to_csv_bytes(df: pd.DataFrame) -> bytes:
    """DataFrame を UTF-8(BOM) の CSV バイト列にする（ダウンロード用）。

    BOM 付きにすることで Excel でそのまま開いても文字化けしない。
    """
    return df.to_csv(index=False).encode("utf-8-sig")
