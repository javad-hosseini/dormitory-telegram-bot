"""Unit tests for cleaned Excel parser, row hashing, and failed rows report generation."""

from pathlib import Path
import openpyxl
from src.services.excel_parser import ExcelParser


def test_parse_cleaned_workbook_and_hashes(tmp_path: Path):
    """Verify parsing valid cleaned rows, ignoring guide sheet, and computing SHA-256 hashes."""
    xlsx_file = tmp_path / "cleaned_dormitory.xlsx"
    wb = openpyxl.Workbook()

    # Sheet 1: Transactions
    ws = wb.active
    ws.title = "Transactions"
    ws.append(["Room", "Resident_Name", "Amount_IRR", "Date", "Peigiri"])
    ws.append([101, "Ali Hosseini", 5000000, "2026-11-04", "987654"])
    ws.append([102, "Sara Karimi", 7500000, "2026-11-04", "123456"])
    ws.append([None, None, None, None, None])  # Empty row to be ignored

    # Sheet 2: Guide tab to be ignored by parser
    ws_guide = wb.create_sheet(title="_AI_EXTRACTION_GUIDE")
    ws_guide.append(["Ignore", "This"])

    wb.save(xlsx_file)

    parser = ExcelParser()
    data = parser.parse_cleaned_workbook(xlsx_file)

    assert data.file_name == "cleaned_dormitory.xlsx"
    assert data.sheet_name == "Transactions"
    assert data.headers == ["Room", "Resident_Name", "Amount_IRR", "Date", "Peigiri"]
    assert len(data.rows) == 2
    assert len(data.row_hashes) == 2

    row1 = data.rows[0]
    assert row1["Room"] == 101
    assert row1["Resident_Name"] == "Ali Hosseini"
    assert row1["Amount_IRR"] == 5000000


def test_generate_failed_rows_report(tmp_path: Path):
    """Verify failed rows report generation with Error_Reason column."""
    parser = ExcelParser()
    output_path = tmp_path / "failed_report.xlsx"

    headers = ["Room", "Resident_Name", "Amount"]
    failed_items = [
        ({"Room": 105, "Resident_Name": "Mohammad", "Amount": "bad_number"}, "Invalid amount format"),
        ({"Room": "", "Resident_Name": "Unknown", "Amount": 4000000}, "Missing room number"),
    ]

    report = parser.generate_failed_rows_report(headers, failed_items, output_path)
    assert report.exists()

    wb = openpyxl.load_workbook(report)
    ws = wb.active
    assert ws.title == "Failed_Transactions"
    assert [cell.value for cell in ws[1]] == ["Room", "Resident_Name", "Amount", "Error_Reason"]
    assert ws.cell(row=2, column=4).value == "Invalid amount format"
    assert ws.cell(row=3, column=4).value == "Missing room number"
