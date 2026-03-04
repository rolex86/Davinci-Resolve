@echo off
setlocal
set "ROOT_DIR=%~dp0"
set "PYTHON_CMD="

where py >nul 2>&1
if %ERRORLEVEL%==0 (
  set "PYTHON_CMD=py -3"
)
if not defined PYTHON_CMD (
  where python >nul 2>&1
  if %ERRORLEVEL%==0 set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  echo Python 3 was not found. Cannot run uninstaller wizard.
  endlocal
  exit /b 1
)

%PYTHON_CMD% "%ROOT_DIR%installer\uninstall_wizard.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Uninstall failed with exit code %EXIT_CODE%.
)

endlocal
exit /b %EXIT_CODE%
