@echo off
title One 4K still - EEVEE (quick test of your setup)
cd /d "%~dp0"
call "%~dp0scripts\windows\find_blender.bat" || exit /b 1
echo.
echo  One 4K still - EEVEE (quick test of your setup)
echo  Estimated time on your PC: under 5 minutes.
echo  The window shows progress after every frame. You can close it at any time:
echo  finished frames are kept and the next run continues where it stopped.
echo.
"%BLENDER%" -b "%~dp0project.blend" -P "%~dp0scripts\render.py" -- --preset HIGH --engine EEVEE --still 75
echo.
echo  Done! Opening the "renders" folder...
start "" "%~dp0renders"
pause
