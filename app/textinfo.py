"""Useful things found in the text of a photo: phone numbers, dates, prices, email addresses and links.

The text comes from the text reader (OCR), so it can contain small mistakes; these rules are kept
simple and a little strict, so that what they find is usually right.
"""

import re
from datetime import date

MONTHS = {name: number for number, names in enumerate([
    ("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",), ("jun", "june"),
    ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"), ("oct", "october"), ("nov", "november"),
    ("dec", "december")], start=1) for name in names}

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)*\.[a-z]{2,}\b", re.IGNORECASE)
_LINK = re.compile(r"\b(?:https?://|www\.)[^\s,;]+|\b[\w-]+\.(?:com|in|org|net|co\.in|gov\.in|edu)(?:/[^\s,;]*)?\b",
                   re.IGNORECASE)
_DATE_NUMBERS = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{4}|\d{2})\b")
_DATE_ISO = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
_DATE_WORDS = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+([a-z]{3,9})\.?,?\s+(\d{4})\b|"
                         r"\b([a-z]{3,9})\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s+(\d{4})\b", re.IGNORECASE)
_PRICE = re.compile(r"(?:₹|rs\.?|inr|\$|€|£|usd|eur)\s?(\d[\d,]*(?:\.\d{1,2})?)(?:\s?/-)?|"
                    r"\b(\d[\d,]*)\s?/-|"
                    r"\b(\d{1,5}[.,]\d{2})\b", re.IGNORECASE)
_PHONE = re.compile(r"(?:\+\d{1,3}[\s.-]?)?\(?\d{2,5}\)?(?:[\s.-]?\d{2,5}){0,3}")
_PHONE_CUE = re.compile(r"(?:tel|phone|ph|mob|mobile|call|contact|whatsapp|fax)\W{0,3}$", re.IGNORECASE)


def _check_date(year: int, month: int, day: int) -> str | None:
    if year < 100:
        year += 2000 if year < 50 else 1900
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def find(text: str) -> dict[str, list[dict]]:
    """{"phones", "dates", "prices", "emails", "links"}: each a list of {"text", ...}, in reading order."""
    found = {"phones": [], "dates": [], "prices": [], "emails": [], "links": []}
    used: list[tuple[int, int]] = []  # parts of the text already taken, so a date is not also a phone number

    def take(kind: str, match: re.Match, **extra) -> None:
        start, end = match.span()
        if any(start < b and a < end for a, b in used):
            return
        used.append((start, end))
        value = match.group(0).strip()
        if all(item["text"] != value for item in found[kind]):
            found[kind].append({"text": value, **extra})

    for match in _EMAIL.finditer(text):
        take("emails", match)
    for match in _LINK.finditer(text):
        take("links", match, url=match.group(0) if "://" in match.group(0) else f"https://{match.group(0)}")
    for match in _PHONE.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        plus = match.group(0).lstrip().startswith("+")
        cue = _PHONE_CUE.search(text[max(0, match.start() - 12):match.start()])
        # A phone number has a "+" or a word like "Tel" in front, or 10-12 digits; shorter runs of digits
        # are usually prices, years or numbers on signs, and longer ones barcodes.
        if (plus and 10 <= len(digits) <= 13) or (cue and 8 <= len(digits) <= 13) or 10 <= len(digits) <= 12:
            take("phones", match, dial=("+" if plus else "") + digits)
    for match in _DATE_ISO.finditer(text):
        if iso := _check_date(int(match[1]), int(match[2]), int(match[3])):
            take("dates", match, iso=iso)
    for match in _DATE_NUMBERS.finditer(text):
        first, second, year = int(match[1]), int(match[2]), int(match[3])
        # India and Europe write the day first; if that can't be a day/month pair, try month first.
        iso = _check_date(year, second, first) or _check_date(year, first, second)
        if iso:
            take("dates", match, iso=iso)
    for match in _DATE_WORDS.finditer(text):
        day, month, year = (match[1], match[2], match[3]) if match[1] else (match[5], match[4], match[6])
        if (number := MONTHS.get(month.lower())) and (iso := _check_date(int(year), number, int(day))):
            take("dates", match, iso=iso)
    for match in _PRICE.finditer(text):
        take("prices", match)
    for items in found.values():  # back in reading order
        items.sort(key=lambda item: text.find(item["text"]))
    return found
