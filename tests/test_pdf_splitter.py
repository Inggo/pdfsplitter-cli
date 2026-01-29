import os
import sys
import tempfile
import re
from pathlib import Path
from reportlab.pdfgen import canvas

import pytest
from pypdf import PdfReader

# Ensure project root is on sys.path so pytest can import pdf_splitter
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pdf_splitter import extract_matches, split_pdf


def make_pdf_with_pages(texts, path):
    c = canvas.Canvas(path)
    for t in texts:
        c.drawString(100, 750, t)
        c.showPage()
    c.save()


def test_extract_matches_and_split(tmp_path):
    # Create a PDF with two student pages
    fd, pdf_path = tempfile.mkstemp(suffix='.pdf')
    os.close(fd)
    texts = [
        "Some header\nName (Last, First, Middle)Doe, John\nStudent No.\n\n1234-56789",
        "Name (Last, First, Middle)Smith, Jane\nStudent No.\n\n2345-67890",
    ]
    make_pdf_with_pages(texts, pdf_path)

    matches = extract_matches(pdf_path)
    assert matches['page_count'] >= 2
    assert len(matches['student_numbers']) == 2
    assert matches['student_numbers'][0] == '1234-56789'

    out_dir = tmp_path / "out"
    out_dir = str(out_dir)
    output_files = split_pdf(pdf_path, out_dir, matches)
    assert len(output_files) == 2
    for f in output_files:
        assert os.path.exists(f)
        reader = PdfReader(f)
        assert len(reader.pages) >= 1

    # cleanup
    os.remove(pdf_path)
    for f in output_files:
        os.remove(f)


def test_sn_pattern_valid_regex():
    """Test that valid regex patterns compile without error"""
    valid_patterns = [
        r"\b\d{4}-\d{5}\b",  # default pattern
        r"\d{4}-\d{5}",
        r"[0-9]{4}-[0-9]{5}",
        r".*",
    ]
    for pattern in valid_patterns:
        try:
            compiled = re.compile(pattern)
            assert compiled is not None
        except re.error:
            pytest.fail(f"Valid pattern '{pattern}' raised re.error")


def test_sn_pattern_invalid_regex():
    """Test that invalid regex patterns raise re.error"""
    invalid_patterns = [
        r"(unclosed",  # unclosed group
        r"[unclosed",  # unclosed bracket
        r"(?P<invalid>unclosed",  # unclosed named group
        r"*invalid",  # nothing to repeat
    ]
    for pattern in invalid_patterns:
        with pytest.raises(re.error):
            re.compile(pattern)