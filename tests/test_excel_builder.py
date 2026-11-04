"""Unit tests for Excel workbook generation with cell-anchored images."""

from pathlib import Path
import openpyxl
from src.database.repository import BlockRecord
from src.services.excel_builder import ExcelBuilder


def test_build_raw_workbook_with_images_and_text(tmp_path: Path, sample_image_path: Path):
    """Verify raw workbook contains proper headers, cell anchors, images, and guide tab."""
    output_file = tmp_path / "raw_output.xlsx"
    builder = ExcelBuilder(max_dimension_px=200)

    blocks = [
        BlockRecord(
            id=1,
            session_id="test_sess",
            row_index=1,
            col_index=1,
            block_type="TEXT",
            text_content="Resident Ali - Room 102 - Rent 5,000,000",
            file_path=None,
            created_at="2026-11-04T12:00:00",
        ),
        BlockRecord(
            id=2,
            session_id="test_sess",
            row_index=1,
            col_index=2,
            block_type="IMAGE",
            text_content=None,
            file_path=str(sample_image_path),
            created_at="2026-11-04T12:01:00",
        ),
        BlockRecord(
            id=3,
            session_id="test_sess",
            row_index=2,
            col_index=1,
            block_type="TEXT",
            text_content="Resident Reza - Room 205",
            file_path=None,
            created_at="2026-11-04T12:02:00",
        ),
    ]

    generated_path = builder.build_raw_workbook("test_sess", blocks, output_file)
    assert generated_path.exists()

    # Inspect generated workbook
    wb = openpyxl.load_workbook(generated_path)
    assert "Raw_Transactions" in wb.sheetnames
    assert "_AI_EXTRACTION_GUIDE" in wb.sheetnames

    ws_raw = wb["Raw_Transactions"]
    # Check headers
    assert ws_raw.cell(row=1, column=1).value == "Resident_Row_ID"
    assert ws_raw.cell(row=1, column=2).value == "Block_1"
    assert ws_raw.cell(row=1, column=3).value == "Block_2"

    # Check Row 1 (Resident 1)
    assert ws_raw.cell(row=2, column=1).value == "Resident_1"
    assert ws_raw.cell(row=2, column=2).value == "Resident Ali - Room 102 - Rent 5,000,000"
    cell_c2_val = str(ws_raw.cell(row=2, column=3).value)
    assert "IMAGE_ANCHOR: C2" in cell_c2_val

    # Verify embedded openpyxl images count
    assert len(ws_raw._images) == 1
    # Verify row height expanded for image row
    assert ws_raw.row_dimensions[2].height >= 250

    # Check Guide Sheet
    ws_guide = wb["_AI_EXTRACTION_GUIDE"]
    guide_cell_val = str(ws_guide.cell(row=7, column=1).value)
    assert "wb._images" in guide_cell_val or "ws._images" in guide_cell_val
