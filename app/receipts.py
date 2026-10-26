"""Reading receipts: which shop, which date, and the total, from the text found in a photo.

Receipts look very different, so these rules aim to be right most of the time and to say "not sure"
(None) otherwise, instead of guessing. The spending page shows what was found next to the photo,
so a mistake is easy to spot.
"""

import re

from app import textinfo

# Words that only appear on bills and receipts (several languages, since shops print what they like).
RECEIPT_WORDS = re.compile(r"\b(total|totaal|subtotal|grand total|net amount|amount payable|to pay|cash|change|"
                           r"gst|cgst|sgst|vat|btw|invoice|receipt|bill|kassabon|qty|mrp)\b", re.IGNORECASE)
TOTAL_LINE = re.compile(r"\b(grand total|net amount|amount payable|total amount|bill amount|to pay|totaal|total)\b",
                        re.IGNORECASE)
NOT_SHOP = re.compile(r"\b(tax invoice|invoice|receipt|bill|gstin|gst|date|tel|phone|time|cashier|kassabon|welcome|"
                      r"thank)\b", re.IGNORECASE)
CURRENCY = {"₹": "₹", "rs": "₹", "inr": "₹", "$": "$", "usd": "$", "€": "€", "eur": "€", "£": "£"}
AMOUNT = re.compile(r"\d[\d,]*(?:[.,]\d{1,2})?")
DATES = re.compile(r"\b\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}\b|\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}:\d{2}(?::\d{2})?\b")


def amount(text: str) -> float | None:
    """'1,250.00' -> 1250.0, '14,21' -> 14.21 (comma decimals, as in Europe), '450' -> 450.0."""
    text = text.strip()
    if "," in text and "." in text:
        text = text.replace(",", "")
    elif re.fullmatch(r"\d+,\d{1,2}", text):
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return round(float(text), 2)
    except ValueError:
        return None


def _shop(lines: list[str]) -> str | None:
    """The shop's name: one of the first lines that is mostly letters and is not a heading like "TAX INVOICE"."""
    for line in lines[:5]:
        letters = sum(c.isalpha() for c in line)
        if letters >= 3 and letters >= len(line.replace(" ", "")) * 0.6 and not NOT_SHOP.search(line):
            name = line.strip(" .:-*|")
            return name.title() if name.isupper() else name
    return None


def _total(lines: list[str]) -> float | None:
    """The amount on the last line that says "total" (or the line after it); otherwise none."""
    for i in range(len(lines) - 1, -1, -1):
        if TOTAL_LINE.search(lines[i]) and not re.search(r"\bsub\s?total\b", lines[i], re.IGNORECASE):
            after = lines[i + 1] if i + 1 < len(lines) else ""
            # The amount is printed on the right, so the text reader can put it just before its label.
            before = lines[i - 1] if i > 0 and re.fullmatch(r"[₹$€£]?\s*[\d,.]+", lines[i - 1]) else ""
            for line in (lines[i], after, before):
                after = DATES.sub(" ", TOTAL_LINE.split(line)[-1])  # a date on the same line is not the total
                found = AMOUNT.findall(after)
                # Prefer an amount with decimals ("450.00"); "(5 items)" or "Qty 2" come before it otherwise.
                best = next((m for m in found if re.search(r"[.,]\d{2}$", m)), found[0] if found else None)
                if best and (value := amount(best)):
                    return value
    return None


def read(text: str) -> dict | None:
    """{"shop", "date", "total", "currency"} if the text looks like a receipt, else None."""
    if not text or len(RECEIPT_WORDS.findall(text)) < 1:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    found = textinfo.find(text)
    total = _total(lines)
    if total is None and len(found["prices"]) < 2:
        return None  # one stray price on a sign is not a receipt
    symbol = next((CURRENCY[s] for s in re.findall(r"₹|\$|€|£|\b(?:rs|inr|usd|eur)\b", text.lower()) if s in CURRENCY),
                  "")
    return {
        "shop": _shop(lines),
        "date": found["dates"][0]["iso"] if found["dates"] else None,
        "total": total,
        "currency": symbol,
    }
