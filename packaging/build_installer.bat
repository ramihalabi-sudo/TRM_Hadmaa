@echo off
rem Builds dist\installer\TRM_HADMAAv1_Setup_<version>.exe: first the EXE folder (build_exe.bat), then the
rem Inno Setup script.  Needs PyInstaller (python -m pip install pyinstaller) and Inno Setup 6 (ISCC.exe).
cd /d "%~dp0\.."
call packaging\build_exe.bat
if errorlevel 1 exit /b 1
set ISCC=
for %%P in ("%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" "%ProgramFiles%\Inno Setup 6\ISCC.exe" "%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe") do if exist %%P set ISCC=%%P
if not defined ISCC (
    echo Inno Setup 6 not found - install it from https://jrsoftware.org/isdl.php
    exit /b 1
)
%ISCC% packaging\TRM_HADMAAv1.iss
if errorlevel 1 exit /b 1
echo.
echo Built dist\installer\
