import os
import tempfile
import zipfile
from pathlib import Path

import pytest

# ensure project root is importable
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pdf_splitter
from pdf_splitter import create_csv, create_zip, upload_files


def test_create_csv_and_zip(tmp_path):
    # create two small files to zip
    f1 = tmp_path / "a.txt"
    f2 = tmp_path / "b.txt"
    f1.write_text("hello")
    f2.write_text("world")

    output_files = [str(f1), str(f2)]
    student_numbers = ["1234-56789", "2345-67890"]
    names = ["Doe, John", "Smith, Jane"]

    # test CSV creation
    csv_path = create_csv(output_files, student_numbers, names)
    assert os.path.exists(csv_path)
    content = open(csv_path, 'r', encoding='utf-8').read()
    assert 'Student Number' in content
    assert '1234-56789' in content

    # test ZIP creation
    zip_path = create_zip(output_files, str(tmp_path))
    assert os.path.exists(zip_path)
    with zipfile.ZipFile(zip_path, 'r') as zf:
        names_in_zip = zf.namelist()
        assert 'a.txt' in names_in_zip
        assert 'b.txt' in names_in_zip

    # cleanup created csv and zip
    os.remove(csv_path)
    os.remove(zip_path)


def test_upload_files_with_mocked_rclone(tmp_path, monkeypatch):
    # create files to upload
    f1 = tmp_path / "one.pdf"
    f2 = tmp_path / "two.pdf"
    f1.write_text("1")
    f2.write_text("2")

    files = [str(f1), str(f2)]
    rclone_remote = 'remote:folder'

    calls = []

    def fake_run_command(cmd):
        # record the command and return a simulated output
        calls.append(list(cmd))
        if cmd[0] == 'rclone' and cmd[1] == 'copy':
            return ''
        if cmd[0] == 'rclone' and cmd[1] == 'link':
            # return a fake public link for the basename
            return f"https://fake/{os.path.basename(cmd[2])}"
        return ''

    monkeypatch.setattr(pdf_splitter, 'run_command', fake_run_command)

    urls = upload_files(files, rclone_remote)

    # ensure we got two links and files were removed
    assert len(urls) == 2
    assert urls[0].startswith('https://fake/')
    assert not os.path.exists(files[0])
    assert not os.path.exists(files[1])

    # ensure rclone copy and link were invoked for each file
    # ensure rclone copy and link were invoked for each file
    copy_calls = [c for c in calls if c[1] == 'copy']
    link_calls = [c for c in calls if c[1] == 'link']
    assert len(copy_calls) == 2
    assert len(link_calls) == 2