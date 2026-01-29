# PDF Splitter (Python)

This is a standalone PDF splitter based on patterns.

## Requirements

- Python 3.8+
- pypdf
- rclone (optional, if you want uploads/links)

## Usage

```
python3 pdf_splitter.py --input path/to/input.pdf --output-dir var/output --as csv
```

To upload outputs via rclone and get links:

```
python3 pdf_splitter.py --input path/to/input.pdf --output-dir var/output --as csv --rclone remote:folder
```

__Notes__

- The script looks for the pattern YYYY-NNNNN and an "overview" text block by default.