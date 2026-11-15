"""Parse restricted, bounded XLSX input and write static synthetic workbooks."""

from dataclasses import dataclass
from datetime import date, datetime, time
from io import BytesIO
from re import fullmatch
from typing import get_args
from xml.etree.ElementTree import ParseError
from zipfile import BadZipFile, ZipFile

from defusedxml.ElementTree import fromstring
from defusedxml.common import DefusedXmlException
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils.cell import column_index_from_string, get_column_letter
from openpyxl.utils.exceptions import InvalidFileException
from pydantic import ValidationError

from workforce_intelligence.dataset import InvalidOperation
from workforce_intelligence.workbook_model import (
    COMMAND_ADAPTER,
    MAX_ROWS,
    MAX_UPLOAD_BYTES,
    METADATA_TITLE,
    MODELS,
    SHEETS,
    SYNTHETIC_NOTICE,
    WORKBOOK_VERSION,
    WorkbookCommand,
    columns_for,
)

INFO_SHEET = "Workbook information"
MAX_PARTS = 80
MAX_PART_BYTES = 2 * 1024 * 1024
MAX_EXPANDED_BYTES = 12 * 1024 * 1024
MAX_COLUMNS = 32
MAX_CELL_CHARS = 300
MAX_EXPORT_ROWS = 1000
_SHEET_NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_XLSX_MAIN = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"


@dataclass(frozen=True)
class BookRow:
    sheet: str
    number: int
    command: WorkbookCommand | None = None
    error: str | None = None


def _check_worksheet(root) -> None:
    # Do not trust the worksheet's dimension hint. Bound each actual row and cell
    # coordinate before allowing openpyxl to iterate or allocate sparse cells.
    last_row = 0
    for row in root.iter(f"{_SHEET_NS}row"):
        raw = row.get("r", "")
        if not fullmatch(r"[1-9][0-9]{0,3}", raw):
            raise InvalidOperation("A worksheet contains an invalid row address.")
        number = int(raw)
        if number <= last_row or number > MAX_ROWS + 1:
            raise InvalidOperation("A worksheet exceeds the address or row limit.")
        last_row = number
        previous_column = 0
        for cell in row:
            if cell.tag != f"{_SHEET_NS}c":
                continue
            coordinate = fullmatch(r"([A-Z]{1,2})([1-9][0-9]{0,3})", cell.get("r", ""))
            if not coordinate or int(coordinate[2]) != number:
                raise InvalidOperation("A worksheet contains an invalid cell address.")
            column = column_index_from_string(coordinate[1])
            if not previous_column < column <= MAX_COLUMNS:
                raise InvalidOperation("A worksheet exceeds the address or column limit.")
            previous_column = column


def _check_zip(content: bytes) -> None:
    if len(content) > MAX_UPLOAD_BYTES:
        raise InvalidOperation("The workbook exceeds the 1 MiB upload limit.")
    with ZipFile(BytesIO(content)) as archive:
        parts = archive.infolist()
        names = {part.filename for part in parts}
        if (
            len(names) != len(parts)
            or len(parts) > MAX_PARTS
            or sum(part.file_size for part in parts) > MAX_EXPANDED_BYTES
        ):
            raise InvalidOperation("The workbook archive is too large or has duplicate parts.")
        for part in parts:
            name = part.filename
            if (
                part.file_size > MAX_PART_BYTES
                or part.flag_bits & 1
                or not fullmatch(r"[A-Za-z0-9_./\[\]-]+", name)
                or any(item in ("", ".", "..") for item in name.split("/"))
                or not name.endswith((".xml", ".rels"))
            ):
                raise InvalidOperation(
                    "Only unencrypted XLSX workbooks without embedded files are supported."
                )
            # Check every XML part before handing the archive to another parser.
            root = fromstring(archive.read(part), forbid_dtd=True)
            if name == "[Content_Types].xml" and not any(
                element.get("PartName") == "/xl/workbook.xml"
                and element.get("ContentType") == _XLSX_MAIN
                for element in root
            ):
                raise InvalidOperation("Upload an ordinary .xlsx workbook, without macros.")
            if name.endswith(".rels") and any(
                child.get("TargetMode", "").lower() == "external" for child in root
            ):
                raise InvalidOperation("External links are not supported in import workbooks.")
            if root.tag == f"{_SHEET_NS}worksheet":
                _check_worksheet(root)
        if not {"[Content_Types].xml", "_rels/.rels", "xl/workbook.xml"} <= names:
            raise InvalidOperation("The file is not a supported .xlsx workbook.")


def _cell_value(cell):
    value = cell.value
    if cell.data_type in ("f", "e"):
        raise ValueError("Use values only. Formulas and spreadsheet errors are not accepted.")
    if isinstance(value, str):
        if len(value) > MAX_CELL_CHARS:
            raise ValueError("Cell text exceeds the allowed length.")
        return value.strip() or None
    if isinstance(value, datetime):
        if value.time() != time():
            raise ValueError("Use a date without a time of day.")
        return value.date()
    return value


def _parse_row(name: str, number: int, columns: tuple[str, ...], cells) -> BookRow:
    try:
        values = [_cell_value(cell) for cell in cells]
    except ValueError as failure:
        return BookRow(name, number, error=str(failure))
    if any(value is not None for value in values[len(columns) :]):
        return BookRow(name, number, error="Unexpected data after the last template column.")
    fields = {key: value for key, value in zip(columns, values, strict=False) if value is not None}
    action = fields.get("action")
    if action not in SHEETS[name]:
        return BookRow(name, number, error=f"Choose a supported action: {', '.join(SHEETS[name])}.")
    model = MODELS[action]
    for key, field in model.model_fields.items():
        value = fields.get(key)
        if (
            field.annotation is bool
            and isinstance(value, str)
            and value.lower() in ("true", "false")
        ):
            fields[key] = value.lower() == "true"
        if (
            value is not None
            and (field.annotation is date or date in get_args(field.annotation))
            and not (
                isinstance(value, date)
                or isinstance(value, str)
                and fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value)
            )
        ):
            return BookRow(name, number, error=f"{key}: use an Excel date or YYYY-MM-DD.")
    try:
        return BookRow(name, number, COMMAND_ADAPTER.validate_python(fields))
    except ValidationError as failure:
        issues = []
        for entry in failure.errors(include_url=False, include_context=False, include_input=False)[
            :5
        ]:
            path = entry["loc"][1:]
            issues.append(
                f"{path[0]}: {entry['msg']}" if path else "Check this action's field combination."
            )
        return BookRow(name, number, error=" ".join(dict.fromkeys(issues)))


def parse_xlsx(content: bytes) -> list[BookRow]:
    try:
        _check_zip(content)
        book = load_workbook(BytesIO(content), read_only=True, data_only=False, keep_links=False)
        try:
            return _parse_workbook(book)
        finally:
            book.close()
    except InvalidOperation:
        raise
    except (
        BadZipFile,
        DefusedXmlException,
        InvalidFileException,
        ParseError,
        KeyError,
        TypeError,
        ValueError,
        IndexError,
        OverflowError,
        OSError,
        NotImplementedError,
    ) as failure:
        raise InvalidOperation(
            "The file could not be read as a supported .xlsx workbook."
        ) from failure


def _parse_workbook(book) -> list[BookRow]:
    if INFO_SHEET not in book.sheetnames or set(book.sheetnames) - {INFO_SHEET, *SHEETS}:
        raise InvalidOperation(
            "Use the Workforce template. The workbook contains missing or unsupported sheets."
        )
    info = book[INFO_SHEET]
    info.reset_dimensions()
    mark = next(info.iter_rows(min_row=1, max_row=1, max_col=2, values_only=True), ())
    if mark != (METADATA_TITLE, WORKBOOK_VERSION):
        raise InvalidOperation(
            "This workbook version is not supported. Download the current template."
        )
    results = []
    for name in SHEETS:
        if name not in book.sheetnames:
            continue
        sheet = book[name]
        if sheet.sheet_state != "visible":
            raise InvalidOperation("Import sheets must be visible.")
        sheet.reset_dimensions()
        rows = sheet.iter_rows(max_col=MAX_COLUMNS)
        header = next(rows, ())
        columns = columns_for(name)
        values = tuple(cell.value for cell in header)
        if values[: len(columns)] != columns or any(
            value is not None for value in values[len(columns) :]
        ):
            raise InvalidOperation(f"Sheet {name} does not have the template's column headers.")
        for number, cells in enumerate(rows, start=2):
            if not any(cell.value is not None for cell in cells):
                continue
            if len(results) >= MAX_ROWS:
                raise InvalidOperation(f"Use at most {MAX_ROWS} data rows in one workbook.")
            results.append(_parse_row(name, number, columns, cells))
    if not results:
        raise InvalidOperation("Add at least one data row to the template.")
    return results


def new_book(description: str) -> Workbook:
    book = Workbook()
    info = book.active
    info.title = INFO_SHEET
    write_row(info, (METADATA_TITLE, WORKBOOK_VERSION), header=True)
    write_row(info, ("Dataset disclosure", SYNTHETIC_NOTICE))
    write_row(info, ("Purpose", description))
    info.column_dimensions["A"].width = 30
    info.column_dimensions["B"].width = 90
    return book


def write_row(sheet, values, *, header: bool = False) -> None:
    # Explicitly use string cells even if a renderer recognises '='. The prefix
    # also protects text when recipients paste it into another spreadsheet.
    escaped = [
        "'" + value
        if isinstance(value, str)
        and (
            value.startswith(("\t", "\r", "\n")) or value.lstrip().startswith(("=", "+", "-", "@"))
        )
        else value
        for value in values
    ]
    sheet.append(escaped)
    for cell, value in zip(sheet[sheet.max_row], escaped, strict=False):
        if isinstance(value, str):
            cell.data_type = "s"
        if header:
            cell.fill = PatternFill("solid", fgColor="184B52")
            cell.font = Font(color="FFFFFF", bold=True)
            cell.alignment = Alignment(vertical="center")


def tab(book: Workbook, title: str, columns, rows=()):
    sheet = book.create_sheet(title)
    write_row(sheet, columns, header=True)
    sheet.freeze_panes = "A2"
    for index, heading in enumerate(columns, 1):
        sheet.column_dimensions[get_column_letter(index)].width = min(
            38, max(17, len(str(heading)) + 4)
        )
    for index, row in enumerate(rows):
        if index >= MAX_EXPORT_ROWS:
            raise InvalidOperation("The export is too large. Narrow the report scope.")
        write_row(sheet, row)
    return sheet


def book_bytes(book: Workbook) -> bytes:
    try:
        target = BytesIO()
        book.save(target)
        return target.getvalue()
    finally:
        book.close()


def template() -> bytes:
    book = new_book("Fill in only the sheets and columns needed for the source action.")
    info = book[INFO_SHEET]
    write_row(
        info,
        ("How to use", "Keep the column names; enter dates as YYYY-MM-DD and use values only."),
    )
    write_row(info, ("Row limit", MAX_ROWS))
    write_row(
        info,
        (
            "Text and IDs",
            "Use fictional display aliases starting with Demo and synthetic reference codes.",
        ),
    )
    for name, actions in SHEETS.items():
        write_row(info, (name, ", ".join(actions)))
        sheet = tab(book, name, columns_for(name))
        for index, column in enumerate(columns_for(name), 1):
            if column == "id" or column.endswith(("_id", "_code")):
                sheet.column_dimensions[get_column_letter(index)].number_format = "@"
    return book_bytes(book)
