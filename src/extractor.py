"""レシート/領収書を Claude API で読み取り、構造化データ(Receipt)に変換する。

- 画像/PDF を1回の呼び出しで「項目抽出 + 勘定科目の推定」まで行う。
- 出力は Pydantic スキーマに固定（Structured Outputs）。
- 金額の検算（税率別内訳の合計＝税込合計か）も提供する。
"""
from __future__ import annotations

import anthropic
from pydantic import BaseModel, Field

from .accounts import DEFAULT_ACCOUNTS
from .loader import to_content_blocks

DEFAULT_MODEL = "claude-sonnet-4-6"


class TaxLine(BaseModel):
    rate: int = Field(description="税率(%)。通常は 10 または 8")
    taxable_amount: int = Field(description="その税率の対象金額(税抜)。円・整数")
    tax_amount: int = Field(description="その税率の消費税額。円・整数")


class Receipt(BaseModel):
    used_date: str = Field(description="利用日。YYYY-MM-DD 形式。不明なら空文字")
    vendor_name: str = Field(description="支払先(店名・会社名)")
    registration_number: str | None = Field(
        description="適格請求書発行事業者の登録番号。'T'+13桁。記載がなければ null"
    )
    total_amount: int = Field(description="税込の合計金額。円・整数")
    tax_lines: list[TaxLine] = Field(
        description="税率別の内訳。10%/8% が混在する場合は税率ごとに分ける"
    )
    payment_method: str | None = Field(
        description="支払方法。現金 / クレジット 等。不明なら null"
    )
    description: str = Field(description="主な品目や摘要を簡潔に")
    suggested_account: str = Field(
        description="推定した勘定科目。必ず候補リストの中から1つ選ぶ"
    )
    account_reason: str = Field(description="その勘定科目を選んだ根拠を簡潔に")
    confidence_notes: str = Field(
        description="読み取りで不確かだった点。問題なければ空文字"
    )


def _system_prompt(accounts: list[str]) -> str:
    return (
        "あなたは日本の経費精算を支援するアシスタントです。"
        "渡された領収書・レシートの画像またはPDFを読み取り、指定のJSON形式で構造化してください。\n"
        "ルール:\n"
        "- 金額はカンマ・通貨記号・全角を除き、整数(円)で返す。\n"
        "- 軽減税率(8%)が含まれる場合は tax_lines を税率ごとに分ける。\n"
        "- registration_number は 'T' + 13桁。記載がなければ null。\n"
        "- suggested_account は次の候補から最も適切なものを必ず1つ選ぶ:\n  "
        + " / ".join(accounts)
        + "\n- 読み取れない項目は推測しない（文字列は空・数値は0・任意項目は null）。"
        "不確かな点は confidence_notes に日本語で書く。"
    )


def extract_receipt(
    data: bytes,
    filename: str,
    *,
    model: str = DEFAULT_MODEL,
    accounts: list[str] | None = None,
    client: anthropic.Anthropic | None = None,
) -> Receipt:
    """1枚のレシート(画像/PDFのバイト列)から Receipt を抽出する。"""
    accounts = accounts or DEFAULT_ACCOUNTS
    client = client or anthropic.Anthropic()  # APIキーは環境変数 ANTHROPIC_API_KEY

    content = to_content_blocks(data, filename)
    content.append(
        {"type": "text", "text": "このレシートを読み取り、指定のJSON形式で返してください。"}
    )

    response = client.messages.parse(
        model=model,
        max_tokens=2048,
        system=_system_prompt(accounts),
        messages=[{"role": "user", "content": content}],
        output_format=Receipt,
    )
    return response.parsed_output


def verify_totals(receipt: Receipt) -> tuple[bool, str]:
    """税率別内訳の合計が税込合計と一致するか検算する。"""
    if not receipt.tax_lines:
        return False, "税率別の内訳が取れていません"
    subtotal = sum(t.taxable_amount + t.tax_amount for t in receipt.tax_lines)
    if subtotal != receipt.total_amount:
        return False, f"内訳合計 {subtotal:,} 円 と 合計 {receipt.total_amount:,} 円 が不一致"
    return True, "OK"
