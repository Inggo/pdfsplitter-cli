#!/usr/bin/env python3
"""
Lightweight PDF splitter.
Usage:
  python3 pdf_splitter.py --input path/to/input.pdf --output-dir var/output --as csv --rclone remote:folder

Requires: pypdf
Install: pip install pypdf
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import List, Optional

from pypdf import PdfReader, PdfWriter

SN_PATTERN = re.compile(r"\b\d{4}-\d{5}\b")
OVERVIEW_PATTERN = re.compile(r"Name \(Last, First, Middle\)(.*?)Student No\.", re.DOTALL)


def send(msg: str):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def run_command(command: List[str]) -> str:
    res = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(command)}\n{res.stderr}")
    return res.stdout.strip()


def extract_matches(pdf_path: str):
    reader = PdfReader(pdf_path)
    page_count = len(reader.pages)
    send(f"{page_count} Pages found")

    page_starts = []
    filenames = []
    student_numbers = []
    names = []

    for index, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        sn_match = SN_PATTERN.search(text)
        overview_match = OVERVIEW_PATTERN.search(text)
        if sn_match and overview_match:
            student_number = sn_match.group(0)
            student_name = overview_match.group(1).strip()
            page_starts.append(index + 1)  # 1-based to match original logic
            student_numbers.append(student_number)
            filenames.append(f"{student_number}.pdf")
            names.append(student_name)
            send(f"Match found: {student_number} - {student_name}")

    return {
        'page_count': page_count,
        'page_starts': page_starts,
        'filenames': filenames,
        'student_numbers': student_numbers,
        'names': names,
    }


def split_pdf(pdf_path: str, output_dir: str, matches: dict) -> List[str]:
    reader = PdfReader(pdf_path)
    page_count = matches['page_count']
    page_starts = matches['page_starts']
    filenames = matches['filenames']

    os.makedirs(output_dir, exist_ok=True)

    output_files = []

    if not page_starts:
        # No matches: write whole file as single output
        out_path = os.path.join(output_dir, os.path.basename(pdf_path))
        send(f"No matches found; copying entire file to {out_path}")
        with open(out_path, 'wb') as f:
            PdfWriter().append_pages_from_reader(reader)
            PdfWriter().write(f)
        return [out_path]

    # Determine ranges for each detected student start
    for i, start in enumerate(page_starts):
        start_idx = start - 1  # zero-based
        if i + 1 < len(page_starts):
            end_idx = page_starts[i+1] - 2  # inclusive (zero-based)
        else:
            end_idx = page_count - 1

        writer = PdfWriter()
        for p in range(start_idx, end_idx + 1):
            writer.add_page(reader.pages[p])

        out_path = os.path.join(output_dir, filenames[i])
        send(f"Creating separate PDF for: {matches['student_numbers'][i]}")
        with open(out_path, 'wb') as f:
            writer.write(f)

        output_files.append(out_path)

    return output_files


def upload_files(files: List[str], rclone_remote: str) -> List[str]:
    urls = []
    for fpath in files:
        basename = os.path.basename(fpath)
        send(f"Uploading: {basename}")
        run_command(['rclone', 'copy', fpath, rclone_remote])
        link = run_command(['rclone', 'link', f"{rclone_remote.rstrip('/')}/{basename}"])
        urls.append(link)
        try:
            os.remove(fpath)
        except Exception:
            pass
    return urls


def create_csv(output: List[str], student_numbers: List[str], names: List[str], out_file: Optional[str] = None) -> str:
    if out_file is None:
        fd, tmp = tempfile.mkstemp(prefix='output_', suffix='.csv')
        os.close(fd)
        out_file = tmp

    with open(out_file, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Student Number', 'Name', 'File'])
        for i, fpath in enumerate(output):
            writer.writerow([student_numbers[i] if i < len(student_numbers) else '',
                             names[i] if i < len(names) else '',
                             fpath])

    return out_file


def create_zip(output_files: List[str], output_dir: str) -> str:
    os.makedirs(output_dir, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='output_', suffix='.zip', dir=output_dir)
    os.close(fd)
    zip_path = tmp
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        for f in output_files:
            zf.write(f, arcname=os.path.basename(f))
    return zip_path


def main():
    global SN_PATTERN, OVERVIEW_PATTERN

    parser = argparse.ArgumentParser(description='Split PDF into per-student PDFs')
    parser.add_argument('--input', '-i', required=True, help='Input PDF path')
    parser.add_argument('--output-dir', '-o', default='output', help='Output directory')
    parser.add_argument('--as', dest='as_type', choices=['csv', 'zip'], default='csv', help='Output as csv or zip')
    parser.add_argument('--rclone', help='Optional rclone remote destination (e.g. remote:folder)')
    parser.add_argument('--sn-pattern', dest='sn_pattern', default=SN_PATTERN.pattern,
                        help='Regex pattern to detect student number (default: %(default)s)')
    parser.add_argument('--overview-pattern', dest='overview_pattern', default=OVERVIEW_PATTERN.pattern,
                        help='Regex pattern to detect overview/name (use a capturing group for the name).')

    # Show help when no arguments are provided
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    args = parser.parse_args()

    # Allow overriding the patterns via CLI while keeping current defaults
    SN_PATTERN = re.compile(args.sn_pattern)
    OVERVIEW_PATTERN = re.compile(args.overview_pattern, re.DOTALL)

    input_pdf = args.input
    output_dir = args.output_dir

    send('Starting job…')

    matches = extract_matches(input_pdf)
    output_files = split_pdf(input_pdf, output_dir, matches)

    if args.rclone:
        send('Uploading output files via rclone')
        uploaded = upload_files(output_files, args.rclone)
    else:
        uploaded = output_files

    if args.as_type == 'zip':
        send('Preparing Zip File')
        zip_path = create_zip(output_files, output_dir)
        send(f'Zip available at: {zip_path}')
        if args.rclone:
            send('Uploading zip via rclone')
            run_command(['rclone', 'copy', zip_path, args.rclone])
            link = run_command(['rclone', 'link', f"{args.rclone.rstrip('/')}/{os.path.basename(zip_path)}"])
            send(f'Zip downloadable at: {link}')
    else:
        csv_path = create_csv(uploaded, matches['student_numbers'], matches['names'])
        if args.rclone:
            run_command(['rclone', 'copy', csv_path, args.rclone])
            link = run_command(['rclone', 'link', f"{args.rclone.rstrip('/')}/{os.path.basename(csv_path)}"])
            send(f'Success! You can download your CSV file here: {link}')
        else:
            send(f'CSV written to: {csv_path}')


if __name__ == '__main__':
    main()
