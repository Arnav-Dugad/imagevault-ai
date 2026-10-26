"""Reading receipts: which shop, which date, the total and the items, from the text found in a photo.
Payment screenshots (UPI apps) count too: who was paid, when and how much.

Receipts look very different, so these rules aim to be right most of the time and to say "not sure"
(None) otherwise, instead of guessing. The spending page shows what was found next to the photo,
so a mistake is easy to spot.
"""

import re
from statistics import median

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
# A line with an item and its price, like "Basmati Rice 5kg   450.00".
ITEM = re.compile(r"^(?P<name>.*?[^\W\d_].*?)\s*[:-]?\s*(?:₹|rs\.?|inr)?\s*(?P<amount>\d[\d,]*[.,]\d{2})$",
                  re.IGNORECASE)
NOT_ITEM = re.compile(r"\b(total|subtotal|sub total|totaal|gst|cgst|sgst|igst|vat|btw|tax|discount|round|cash|change|"
                      r"card|upi|paid|balance|amount|date|time|tel|phone|bill|invoice|savings?|mrp)\b", re.IGNORECASE)
# Sizes and counts that differ between visits ("Atta 10kg", "Masala Dosa x2"); left out to compare items.
QUANTITY = re.compile(r"\b(?:x\s?\d+|\d+(?:[.,]\d+)?\s?(?:kg|g|gm|gms|l|ltr|ml|pcs?|nos|pack)?|dozen|pack)\b",
                      re.IGNORECASE)
# A payment screenshot (a UPI app) needs two of these.
PAYMENT_CUES = re.compile(r"\b(upi|paid to|sent to|payment successful|payment received|paid successfully|"
                          r"transaction id|txn id|upi ref|ref(?:erence)? no|debited from|money sent)\b", re.IGNORECASE)
PAYEE = re.compile(r"^(?:paid to|sent to|to)\b\s*:?\s*(.*)$", re.IGNORECASE)
RUPEES = re.compile(r"(?:₹|rs\.?|inr)\s?(\d[\d,]*(?:\.\d{1,2})?)", re.IGNORECASE)
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


def rows(words: list[dict]) -> list[str]:
    """The words put back into rows as printed, left to right.

    The text reader reads a price and its item as two separate lines (they are far apart), and a photo
    is often a little turned. So the slope of the lines is measured from the words of each line, the
    words are straightened with it, and words at the same height become one row again.
    """
    if not words:
        return []
    placed = [(w["text"], w["box"][0] + w["box"][2] / 2, w["box"][1] + w["box"][3] / 2, w["box"][3], w.get("line", 0))
              for w in words]
    slopes = []
    for line in {p[4] for p in placed}:
        same = sorted((p for p in placed if p[4] == line), key=lambda p: p[1])
        if len(same) >= 2 and same[-1][1] - same[0][1] > 0.05:
            slopes.append((same[-1][2] - same[0][2]) / (same[-1][1] - same[0][1]))
    slope = max(-0.3, min(0.3, median(slopes))) if slopes else 0.0
    height = median(p[3] for p in placed)
    result: list[list] = []  # [[straightened height, [(x, text), ...]], ...]
    for text, x, y, _, _ in sorted(placed, key=lambda p: p[2] - slope * p[1]):
        level = y - slope * x
        if result and abs(level - result[-1][0]) <= height * 0.5:
            row = result[-1]
            row[0] = (row[0] * len(row[1]) + level) / (len(row[1]) + 1)
            row[1].append((x, text))
        else:
            result.append([level, [(x, text)]])
    return [" ".join(text for _, text in sorted(row[1])) for row in result]


def _items(lines: list[str]) -> list[dict]:
    """The items bought: rows with a name and a price, above the total."""
    last = max((i for i, line in enumerate(lines) if TOTAL_LINE.search(line)), default=len(lines))
    items = []
    for line in lines[:last]:
        match = ITEM.match(line)
        if not match or NOT_ITEM.search(line):
            continue
        name = match["name"].strip(" .:-*|")
        if sum(c.isalpha() for c in name) >= 3 and (value := amount(match["amount"])):
            items.append({"name": name.title() if name.isupper() else name, "amount": value})
    return items


def item_name(name: str) -> str:
    """An item's name without sizes and counts, so "Atta 10kg" and "ATTA 5kg" are the same item."""
    return re.sub(r"\s+", " ", QUANTITY.sub(" ", name)).strip(" .:-*|").title() or name


def _payment(text: str, lines: list[str]) -> dict | None:
    """A payment screenshot from a UPI app: who was paid, how much and when."""
    if len({cue.lower() for cue in PAYMENT_CUES.findall(text)}) < 2:
        return None
    payee = None
    for i, line in enumerate(lines):
        if match := PAYEE.match(line):
            name = match[1].strip() or (lines[i + 1] if i + 1 < len(lines) else "")
            if sum(c.isalpha() for c in name) >= 3:
                payee = name.strip(" .:-*|")
                break
    rupees = RUPEES.search(text)
    bare = next((line for line in lines if re.fullmatch(r"\d[\d,]*(?:\.\d{1,2})?", line)), None)
    found = textinfo.find(text)
    return {
        "shop": payee,
        "date": found["dates"][0]["iso"] if found["dates"] else None,
        "total": amount(rupees[1] if rupees else bare) if (rupees or bare) else None,
        "currency": "₹",
        "kind": "payment",
        "items": [],
    }


def read(text: str, words: list[dict] | None = None) -> dict | None:
    """{"shop", "date", "total", "currency", "kind", "items"} if the text looks like a receipt or a
    payment screenshot, else None. With the words' positions, prices are matched to their items."""
    if words:
        text = "\n".join(rows(words))
    if not text:
        return None
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if payment := _payment(text, lines):
        return payment
    if len(RECEIPT_WORDS.findall(text)) < 1:
        return None
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
        "kind": "receipt",
        "items": _items(lines),
    }
