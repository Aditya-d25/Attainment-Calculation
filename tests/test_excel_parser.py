"""Tests for the Excel parser."""

import pytest
import os
from services.excel_parser import parse_reference_excel


SAMPLE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "sample_data",
    "reference_mapping.xlsx",
)


class TestParseReferenceExcel:
    @pytest.fixture(autouse=True)
    def check_sample_exists(self):
        if not os.path.exists(SAMPLE_FILE):
            pytest.skip("Sample file not found")

    def test_parses_successfully(self):
        result = parse_reference_excel(SAMPLE_FILE)
        assert len(result.errors) == 0
        assert len(result.co_codes) > 0
        assert len(result.po_codes) > 0

    def test_extracts_correct_cos(self):
        result = parse_reference_excel(SAMPLE_FILE)
        assert "CO206.1" in result.co_codes
        assert "CO206.6" in result.co_codes
        assert len(result.co_codes) == 6

    def test_extracts_po_headers(self):
        result = parse_reference_excel(SAMPLE_FILE)
        assert "PO1" in result.po_codes
        assert "PO11" in result.po_codes
        assert len(result.po_codes) == 11

    def test_extracts_pso_headers(self):
        result = parse_reference_excel(SAMPLE_FILE)
        assert "PSO1" in result.pso_codes
        assert "PSO3" in result.pso_codes
        assert len(result.pso_codes) == 3

    def test_mapping_values(self):
        result = parse_reference_excel(SAMPLE_FILE)

        # CO206.1 -> PO1 = 2
        assert result.mappings.get(("CO206.1", "PO1")) == 2

        # CO206.1 -> PO6 = 0 (was "-")
        assert result.mappings.get(("CO206.1", "PO6")) == 0

        # CO206.5 -> PO1 = 3
        assert result.mappings.get(("CO206.5", "PO1")) == 3

    def test_total_mappings(self):
        result = parse_reference_excel(SAMPLE_FILE)
        # 6 COs × 14 PO/PSOs = 84 total
        assert len(result.mappings) == 84

    def test_co_descriptions(self):
        result = parse_reference_excel(SAMPLE_FILE)
        assert "CO206.1" in result.co_descriptions
        assert "sorting" in result.co_descriptions["CO206.1"].lower()

    def test_invalid_file(self):
        result = parse_reference_excel("/nonexistent/file.xlsx")
        assert len(result.errors) > 0

    def test_sheet_name(self):
        result = parse_reference_excel(SAMPLE_FILE)
        assert result.sheet_name != ""
