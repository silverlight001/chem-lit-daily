@echo off
cd /d "%~dp0"
pythonw open_chem_lit_daily.pyw
if errorlevel 1 (
    python open_chem_lit_daily.pyw
)
