@echo off
REM Batch file to run pdf_splitter.py with dragged input file

REM Change this to the Python executable if needed
SET PYTHON_EXE=py

REM Change this to the script path
SET SCRIPT_PATH=C:\scripts\pdf_splitter.py

REM Edit default script as needed
%PYTHON_EXE% "%SCRIPT_PATH%" --input "%~1" --as csv --rclone gdrive:"TEST OUTPUTS"

PAUSE
