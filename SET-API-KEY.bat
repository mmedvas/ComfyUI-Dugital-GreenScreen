@echo off
title Dugital Green Screen - MiniMax API key
echo.
echo   Dugital Green Screen - set your MiniMax API key
echo   -----------------------------------------------
echo   1. Copy your key from platform.minimax.io  (Account ^> API Keys)
echo   2. Right-click in this window (or press Ctrl+V) to paste it
echo   3. Press Enter
echo.
set "KEY="
set /p "KEY=  API key: "
if "%KEY%"=="" goto nokey
<nul set /p "=%KEY%" > "%~dp0minimax_api_key.txt"
echo.
echo   Saved. Close this window and restart ComfyUI - you are ready.
echo   The key is kept only in this folder. It is never stored in your images or workflows.
echo.
pause
exit /b 0
:nokey
echo.
echo   No key was entered, so nothing was saved. Double-click this file again to retry.
echo.
pause
exit /b 1
