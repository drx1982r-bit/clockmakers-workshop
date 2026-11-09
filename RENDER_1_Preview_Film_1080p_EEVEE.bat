@echo off
title Preview film - 1080p, EEVEE (fastest)
cd /d "%~dp0"
call "%~dp0scripts\windows\find_blender.bat" || exit /b 1
echo.
echo  Preview film - 1080p, EEVEE (fastest)
echo  Estimated time on your PC: about 1-3 hours.
echo  The window shows progress after every frame. You can close it at any time:
echo  finished frames are kept and the next run continues where it stopped.
echo.
"%BLENDER%" -b "%~dp0project.blend" -P "%~dp0scripts\render.py" -- --preset LOW --engine EEVEE --encode
echo.
echo  Done! Opening the "renders" folder...
start "" "%~dp0renders"
pause
