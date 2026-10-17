@echo off
cd /d "%~dp0"
rem No arguments: start the GUI without a console window. With arguments (--cli, --list): run in this console.
if "%~1"=="" (
    start "" pythonw TRM_HADMAAv1.pyw
) else (
    python run_trm4.py %*
)
