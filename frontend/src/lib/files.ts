/** Small files made in the browser: a contact card (.vcf), a calendar reminder (.ics) and a spreadsheet (.csv). */

export function download(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const link = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

const safe = (value: string) => value.replace(/[\\;,]/g, (c) => `\\${c}`).replace(/\r?\n/g, "\\n");
const fileName = (value: string) => value.replace(/[^\w\- ]+/g, "").trim().slice(0, 40) || "imagevault";

/** A contact card that phones and Outlook/Google Contacts can import. */
export function contactCard(name: string, phone: string, note: string) {
  const card = ["BEGIN:VCARD", "VERSION:3.0", `FN:${safe(name)}`, `N:${safe(name)};;;;`, `TEL;TYPE=CELL:${phone}`,
    `NOTE:${safe(note)}`, "END:VCARD", ""].join("\r\n");
  download(`${fileName(name)}.vcf`, card, "text/vcard");
}

/** An all-day calendar reminder for a date found in a photo. */
export function calendarEvent(title: string, isoDate: string, note: string) {
  const day = isoDate.replace(/-/g, "");
  const next = new Date(`${isoDate}T00:00:00Z`);
  next.setUTCDate(next.getUTCDate() + 1);
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d+/, "");
  const event = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ImageVault//EN", "BEGIN:VEVENT",
    `UID:${day}-${Math.random().toString(36).slice(2)}@imagevault`, `DTSTAMP:${stamp}`,
    `DTSTART;VALUE=DATE:${day}`, `DTEND;VALUE=DATE:${next.toISOString().slice(0, 10).replace(/-/g, "")}`,
    `SUMMARY:${safe(title)}`, `DESCRIPTION:${safe(note)}`,
    "BEGIN:VALARM", "TRIGGER:-PT9H", "ACTION:DISPLAY", `DESCRIPTION:${safe(title)}`, "END:VALARM",
    "END:VEVENT", "END:VCALENDAR", ""].join("\r\n");
  download(`${fileName(title)}.ics`, event, "text/calendar");
}

/** Rows to a CSV file that Excel and Google Sheets open. */
export function csvFile(name: string, rows: (string | number | null)[][]) {
  const cell = (value: string | number | null) => {
    const text = value === null ? "" : String(value);
    return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
  };
  download(name, "﻿" + rows.map((row) => row.map(cell).join(",")).join("\r\n"), "text/csv");
}
