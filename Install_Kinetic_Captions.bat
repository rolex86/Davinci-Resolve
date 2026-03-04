@echo off
setlocal
set "ROOT_DIR=%~dp0"

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  py -3 "%ROOT_DIR%installer\install_wizard.py" %*
) else (
  python "%ROOT_DIR%installer\install_wizard.py" %*
)
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Installation failed with exit code %EXIT_CODE%.
)

endlocal
exit /b %EXIT_CODE%
