@echo off
setlocal
set "ROOT_DIR=%~dp0"
set "PYTHONPATH=%ROOT_DIR%src;%PYTHONPATH%"

python "%ROOT_DIR%resolve\\auto_kinetic_captions.py" %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo run_resolve_pipeline failed with exit code %EXIT_CODE%.
)

endlocal
exit /b %EXIT_CODE%
