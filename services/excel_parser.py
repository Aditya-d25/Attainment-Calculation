"""
Excel workbook parser for extracting reference CO-PO mappings.

Supports:
- Auto-detecting the mapping sheet by searching for PO headers
- Extracting CO identifiers from row labels
- Extracting PO/PSO headers from column headers
- Parsing mapping values (1, 2, 3, "-")
- Robust header detection (not hardcoded row numbers)
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

logger = logging.getLogger(__name__)


class ExcelParseResult:
    """Structured result from parsing a reference Excel workbook."""

    def __init__(self):
        self.co_codes: List[str] = []
        self.co_descriptions: Dict[str, str] = {}
        self.po_codes: List[str] = []
        self.pso_codes: List[str] = []
        self.mappings: Dict[Tuple[str, str], int] = {}  # (co_code, po/pso_code) -> level
        self.sheet_name: str = ""
        self.errors: List[str] = []

    def to_dict(self) -> Dict:
        return {
            "co_codes": self.co_codes,
            "co_descriptions": self.co_descriptions,
            "po_codes": self.po_codes,
            "pso_codes": self.pso_codes,
            "mappings": {
                f"{k[0]}-{k[1]}": v for k, v in self.mappings.items()
            },
            "sheet_name": self.sheet_name,
            "errors": self.errors,
            "total_mappings": len(self.mappings),
        }


def _find_mapping_sheet(wb: openpyxl.Workbook) -> Optional[Worksheet]:
    """
    Find the sheet containing CO-PO mappings by looking for PO headers.

    Searches for sheets with cells containing "PO1", "PO2", etc.
    """
    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        for row in ws.iter_rows(min_row=1, max_row=min(20, ws.max_row or 20), values_only=False):
            for cell in row:
                if cell.value and isinstance(cell.value, str):
                    val = cell.value.strip().upper()
                    if val == "PO1" or val == "PO 1":
                        logger.info(f"Found mapping sheet: {sheet_name}")
                        return ws

    # Fallback: check for sheet names containing mapping-related keywords
    keywords = ["attainment", "mapping", "co-po", "co_po", "matrix"]
    for sheet_name in wb.sheetnames:
        for kw in keywords:
            if kw.lower() in sheet_name.lower():
                logger.info(f"Found mapping sheet by name: {sheet_name}")
                return wb[sheet_name]

    return None


def _find_header_row(ws: Worksheet) -> Optional[int]:
    """Find the row containing PO1, PO2, etc. headers."""
    for row_idx in range(1, min(25, (ws.max_row or 25) + 1)):
        for col_idx in range(1, min(30, (ws.max_column or 30) + 1)):
            cell = ws.cell(row=row_idx, column=col_idx)
            if cell.value and isinstance(cell.value, str):
                val = cell.value.strip().upper()
                if val == "PO1" or val == "PO 1":
                    return row_idx
    return None


def _extract_po_pso_headers(ws: Worksheet, header_row: int) -> Dict[int, Tuple[str, str]]:
    """
    Extract PO and PSO column headers.

    Returns dict mapping column_index -> (code, type) where type is "PO" or "PSO".
    """
    headers = {}
    for col_idx in range(1, min(30, (ws.max_column or 30) + 1)):
        cell = ws.cell(row=header_row, column=col_idx)
        if cell.value and isinstance(cell.value, str):
            val = cell.value.strip().upper()
            # Match PO1, PO2, ..., PO11, PSO1, PSO2, PSO3
            po_match = re.match(r'^PO\s*(\d+)$', val)
            pso_match = re.match(r'^PSO\s*(\d+)$', val)
            if po_match:
                code = f"PO{po_match.group(1)}"
                headers[col_idx] = (code, "PO")
            elif pso_match:
                code = f"PSO{pso_match.group(1)}"
                headers[col_idx] = (code, "PSO")
    return headers


def _parse_mapping_value(value) -> int:
    """
    Parse a mapping cell value to an integer level.

    Handles: 1, 2, 3, "-", "", None, float values.
    """
    if value is None:
        return 0

    if isinstance(value, (int, float)):
        v = int(value)
        if v in (0, 1, 2, 3):
            return v
        return 0

    if isinstance(value, str):
        val = value.strip()
        if val in ("", "-", "–", "—", "N/A", "n/a", "NA", "na"):
            return 0
        try:
            v = int(float(val))
            if v in (0, 1, 2, 3):
                return v
        except (ValueError, TypeError):
            pass

    return 0


def _extract_co_code(cell_value) -> Optional[str]:
    """Extract a CO code from a cell value."""
    if cell_value is None:
        return None

    val = str(cell_value).strip()

    # Match patterns like: CO1, CO206.1, CO 1, CO-1, etc.
    match = re.match(r'(CO\s*[\d.]+)', val, re.IGNORECASE)
    if match:
        code = match.group(1).upper().replace(" ", "")
        return code

    return None


def parse_reference_excel(file_path: str) -> ExcelParseResult:
    """
    Parse a reference Excel workbook to extract CO-PO mappings.

    Args:
        file_path: Path to the .xlsx file.

    Returns:
        ExcelParseResult with extracted data.
    """
    result = ExcelParseResult()

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True)
    except Exception as e:
        result.errors.append(f"Failed to open workbook: {str(e)}")
        return result

    # Find the mapping sheet
    ws = _find_mapping_sheet(wb)
    if ws is None:
        result.errors.append(
            "Could not find a sheet containing CO-PO mapping data. "
            "Expected a sheet with PO1, PO2, ... headers."
        )
        return result

    result.sheet_name = ws.title

    # Find header row
    header_row = _find_header_row(ws)
    if header_row is None:
        result.errors.append(
            f"Could not find PO header row in sheet '{ws.title}'. "
            "Expected cells containing 'PO1', 'PO2', etc."
        )
        return result

    # Extract PO/PSO column headers
    po_pso_headers = _extract_po_pso_headers(ws, header_row)
    if not po_pso_headers:
        result.errors.append("No PO or PSO headers found in the header row.")
        return result

    result.po_codes = [
        code for _, (code, t) in sorted(po_pso_headers.items()) if t == "PO"
    ]
    result.pso_codes = [
        code for _, (code, t) in sorted(po_pso_headers.items()) if t == "PSO"
    ]

    logger.info(
        f"Found {len(result.po_codes)} POs and {len(result.pso_codes)} PSOs "
        f"in header row {header_row}"
    )

    # Find CO identifier column (usually column 1 or 2)
    co_col = None
    for col_idx in range(1, min(5, (ws.max_column or 5) + 1)):
        for row_idx in range(header_row + 1, min(header_row + 20, (ws.max_row or 50) + 1)):
            cell = ws.cell(row=row_idx, column=col_idx)
            if _extract_co_code(cell.value):
                co_col = col_idx
                break
        if co_col:
            break

    if co_col is None:
        result.errors.append(
            "Could not find CO identifiers (e.g., CO1, CO206.1) in the data rows."
        )
        return result

    # Check for description column (usually next to CO code)
    desc_col = None
    for col_idx in range(co_col + 1, min(co_col + 3, (ws.max_column or 10) + 1)):
        cell = ws.cell(row=header_row + 1, column=col_idx)
        if cell.value and isinstance(cell.value, str) and len(cell.value.strip()) > 10:
            if col_idx not in po_pso_headers:
                desc_col = col_idx
                break

    # Extract CO rows and mapping values
    for row_idx in range(header_row + 1, (ws.max_row or 100) + 1):
        co_cell = ws.cell(row=row_idx, column=co_col)
        co_code = _extract_co_code(co_cell.value)

        if not co_code:
            # Check if this is just an empty row or end of data
            has_any_data = any(
                ws.cell(row=row_idx, column=c).value is not None
                for c in po_pso_headers.keys()
            )
            if not has_any_data:
                continue
            else:
                # Row has data but no CO code — skip
                continue

        result.co_codes.append(co_code)

        # Extract description if available
        if desc_col:
            desc_cell = ws.cell(row=row_idx, column=desc_col)
            if desc_cell.value:
                result.co_descriptions[co_code] = str(desc_cell.value).strip()

        # Extract mapping values
        for col_idx, (po_pso_code, po_pso_type) in po_pso_headers.items():
            cell = ws.cell(row=row_idx, column=col_idx)
            level = _parse_mapping_value(cell.value)
            result.mappings[(co_code, po_pso_code)] = level

    logger.info(
        f"Extracted {len(result.co_codes)} COs and "
        f"{len(result.mappings)} mapping values from '{ws.title}'"
    )

    wb.close()
    return result
