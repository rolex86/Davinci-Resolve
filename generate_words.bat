@echo off
setlocal
set "ROOT_DIR=%~dp0"
set "PYTHONPATH=%ROOT_DIR%src;%PYTHONPATH%"

python -m kinetic_captions.cli %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo generate_words failed with exit code %EXIT_CODE%.
)

endlocal
exit /b %EXIT_CODE%
