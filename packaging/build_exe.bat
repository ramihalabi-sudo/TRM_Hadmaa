@echo off
rem Builds dist\TRM_HADMAAv1\TRM_HADMAAv1.exe (one folder; copy the whole folder to another PC - no Python needed).
rem Needs PyInstaller in the Python that runs it:  python -m pip install pyinstaller
cd /d "%~dp0\.."
rem prefer the py launcher: "python" can be the Microsoft Store placeholder
set PY=python
where py >nul 2>nul && set PY=py -3
%PY% -m PyInstaller --noconfirm --distpath dist --workpath build packaging\TRM_HADMAAv1.spec
if errorlevel 1 exit /b 1
echo.
echo Built dist\TRM_HADMAAv1\TRM_HADMAAv1.exe
