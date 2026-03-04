@echo off
setlocal
set "ROOT_DIR=%~dp0"
set "PYTHONPATH=%ROOT_DIR%src;%PYTHONPATH%"

python -m kinetic_captions.model_manager %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo install_whisper_model failed with exit code %EXIT_CODE%.
)

endlocal
exit /b %EXIT_CODE%
