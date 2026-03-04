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
  echo Python 3 was not found on this computer.
  where winget >nul 2>&1
  if %ERRORLEVEL%==0 (
    set /p INSTALL_PY=Install Python automatically using winget? [Y/n]:
    if /I "%INSTALL_PY%"=="N" goto :NO_PYTHON
    if "%INSTALL_PY%"=="" set "INSTALL_PY=Y"
    if /I "%INSTALL_PY%"=="Y" (
      winget install --id Python.Python.3.12 -e --source winget
      where py >nul 2>&1
      if %ERRORLEVEL%==0 set "PYTHON_CMD=py -3"
      if not defined PYTHON_CMD (
        where python >nul 2>&1
        if %ERRORLEVEL%==0 set "PYTHON_CMD=python"
      )
    )
  ) else (
    echo winget is not available, cannot auto-install Python.
  )
)

if not defined PYTHON_CMD goto :NO_PYTHON

%PYTHON_CMD% "%ROOT_DIR%installer\install_wizard.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo Installation failed with exit code %EXIT_CODE%.
)

endlocal
exit /b %EXIT_CODE%

:NO_PYTHON
echo.
echo Python 3.10+ is required for installer runtime.
echo Install Python, then run this installer again.
endlocal
exit /b 1
