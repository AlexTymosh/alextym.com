"""Downloadable Excel XLSX and iCalendar ICS exports for local synthetic fleet demo.

Use Python's standard library to keep this module deployable without extra packages.
"""

from __future__ import annotations

import io
import zipfile
from datetime import date, datetime, timedelta, timezone
from xml.sax.saxutils import escape


SPREADSHEET_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _col(n: int) -> str:
    letters = ""
    while n:
        n, remainder = divmod(n - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _cell(value: object, row: int, col: int, header: bool = False) -> str:
    ref = f"{_col(col)}{row}"
    style = ' s="1"' if header else (' s="2"' if row % 2 == 0 else "")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return f'<c r="{ref}"{style}><v>{value}</v></c>'
    # Inline strings are never interpreted by Excel as potentially dangerous formulas.
    val = escape(str(value if value is not None else ""))
    return f'<c r="{ref}" t="inlineStr"{style}><is><t>{val}</t></is></c>'


def _sheet(columns: list[str], values: list[list[object]]) -> str:
    widths = [
        min(
            48,
            max(
                14,
                len(str(column)) + 4,
                *(
                    min(
                        48,
                        len(str(row[index] if index < len(row) and row[index] is not None else ""))
                        + 2,
                    )
                    for row in values[:150]
                ),
            ),
        )
        for index, column in enumerate(columns)
    ]
    cols = "".join(
        f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>'
        for i, width in enumerate(widths, 1)
    )
    entries = [columns, *values]
    cells = "".join(
        f'<row r="{i}">' + "".join(_cell(v, i, j, i == 1) for j, v in enumerate(row, 1)) + "</row>"
        for i, row in enumerate(entries, 1)
    )
    last = f"{_col(len(columns))}{max(len(entries), 1)}"
    return (
        f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<worksheet xmlns="{SPREADSHEET_NS}">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        f'<cols>{cols}</cols><sheetData>{cells}</sheetData><autoFilter ref="A1:{last}"/>'
        "</worksheet>"
    )


def build_xlsx(snapshot: dict) -> bytes:
    """Build formatted XLSX from the current database snapshot (not hard-coded sample rows)."""
    vehicles = snapshot["vehicles"]
    by_id = {v["id"]: v["registration"] for v in vehicles}
    contacts = {c["id"]: c for c in snapshot["contacts"]}
    tabs = [
        (
            "Vehicles",
            [
                "Registration",
                "Model",
                "Status",
                "Severity",
                "Problem",
                "Scenario",
                "Workshop",
                "VOR days",
                "Next action",
                "Responsible",
                "Action due",
                "MOT due",
                "Inspection due",
                "Service due",
                "Odometer (mi)",
            ],
            [
                [
                    v.get(k)
                    for k in (
                        "registration",
                        "model",
                        "availability_status",
                        "severity",
                        "issue",
                        "scenario",
                        "garage",
                        "vor_days",
                        "next_action",
                        "responsible",
                        "action_due",
                        "mot_due",
                        "inspection_due",
                        "service_due",
                        "odometer_miles",
                    )
                ]
                for v in vehicles
            ],
        ),
        (
            "Tickets",
            [
                "Ticket",
                "Vehicle",
                "Type",
                "Title",
                "Status",
                "Severity",
                "Scenario",
                "Status register",
                "HOTH",
            ],
            [
                [
                    t["id"],
                    by_id.get(t["vehicle_id"], ""),
                    t["kind"],
                    t["title"],
                    t["status"],
                    t["severity"],
                    t["scenario"],
                    t["key2_reference"],
                    t["hoth_reference"],
                ]
                for t in snapshot["tickets"]
            ],
        ),
        (
            "Activity",
            [
                "Event ID",
                "Vehicle",
                "Ticket",
                "Channel",
                "Author",
                "Date / time",
                "Subject",
                "Message",
                "Recipient",
                "Direction",
            ],
            [
                [
                    e["id"],
                    by_id.get(e["vehicle_id"], ""),
                    e["ticket_id"],
                    e["kind"],
                    e["author"],
                    e["created_at"],
                    e["subject"],
                    e["body"],
                    e["recipient_email"],
                    e["direction"],
                ]
                for e in snapshot["events"]
            ],
        ),
        (
            "Bookings",
            ["Vehicle", "Service type", "Booking date", "Workshop", "Status"],
            [
                [
                    by_id.get(b["vehicle_id"], ""),
                    b["kind"],
                    b["booked_date"],
                    b["garage"],
                    b["status"],
                ]
                for b in snapshot["bookings"]
            ],
        ),
        (
            "Subscribers",
            ["Vehicle", "Name", "Role", "Email"],
            [
                [
                    by_id.get(s["vehicle_id"], ""),
                    contacts.get(s["contact_id"], {}).get("name", ""),
                    contacts.get(s["contact_id"], {}).get("role", ""),
                    contacts.get(s["contact_id"], {}).get("email", ""),
                ]
                for s in snapshot["subscriptions"]
            ],
        ),
    ]
    names = [n for n, _, _ in tabs]
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for i in range(1, len(tabs) + 1)
            )
            + "</Types>",
        )
        z.writestr(
            "_rels/.rels",
            f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{PKG_REL_NS}">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            "</Relationships>",
        )
        z.writestr(
            "xl/workbook.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="{SPREADSHEET_NS}" xmlns:r="{REL_NS}"><sheets>'
            + "".join(
                f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
                for i, name in enumerate(names, 1)
            )
            + "</sheets></workbook>",
        )
        z.writestr(
            "xl/_rels/workbook.xml.rels",
            f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{PKG_REL_NS}">'
            + "".join(
                f'<Relationship Id="rId{i}" Type="{REL_NS}/worksheet" Target="worksheets/sheet{i}.xml"/>'
                for i in range(1, len(tabs) + 1)
            )
            + f'<Relationship Id="rId{len(tabs) + 1}" Type="{REL_NS}/styles" Target="styles.xml"/>'
            + "</Relationships>",
        )
        # Two simple styles: header with sage fill and white text, alternating pale rows.
        z.writestr(
            "xl/styles.xml",
            f'<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="{SPREADSHEET_NS}">'
            '<fonts count="2"><font><sz val="11"/><name val="Aptos"/></font><font><b/><sz val="11"/><color rgb="FFFFFFFF"/><name val="Aptos"/></font></fonts>'
            '<fills count="4"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF596246"/></patternFill></fill><fill><patternFill patternType="solid"><fgColor rgb="FFF3F5EE"/></patternFill></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="2" borderId="0" xfId="0" applyFill="1"/><xf numFmtId="0" fontId="0" fillId="3" borderId="0" xfId="0" applyFill="1"/></cellXfs>'
            "</styleSheet>",
        )
        for i, (_, columns, rows) in enumerate(tabs, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", _sheet(columns, rows))
    return out.getvalue()


def _ics_escape(raw: object) -> str:
    return (
        str(raw if raw is not None else "")
        .replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\r", "")
        .replace("\n", "\\n")
    )


def build_ics(snapshot: dict) -> bytes:
    """All-day events compatible with Outlook and Google Calendar import."""
    by_id = {v["id"]: v["registration"] for v in snapshot["vehicles"]}
    parts = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Fleet VOR Hub//Synthetic Demo Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Fleet VOR Demo",
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for b in snapshot["bookings"]:
        try:
            start = date.fromisoformat(b["booked_date"])
        except ValueError:
            continue
        next_day = start + timedelta(days=1)
        parts.extend(
            [
                "BEGIN:VEVENT",
                f"UID:vor-demo-{b['id']}@alextym.com",
                f"DTSTAMP:{stamp}",
                f"DTSTART;VALUE=DATE:{start:%Y%m%d}",
                f"DTEND;VALUE=DATE:{next_day:%Y%m%d}",
                f"SUMMARY:{_ics_escape(b['kind'] + ' · ' + by_id.get(b['vehicle_id'], 'Vehicle'))}",
                f"LOCATION:{_ics_escape(b['garage'])}",
                f"DESCRIPTION:{_ics_escape('Fleet VOR Hub DEMO · ' + b['status'])}",
                "END:VEVENT",
            ]
        )
    parts.append("END:VCALENDAR")
    return ("\r\n".join(parts) + "\r\n").encode("utf-8")
