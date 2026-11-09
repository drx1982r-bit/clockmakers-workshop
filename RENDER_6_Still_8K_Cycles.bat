@echo off
title One 8K hero still - Ultra quality (Cycles)
cd /d "%~dp0"
call "%~dp0scripts\windows\find_blender.bat" || exit /b 1
echo.
echo  One 8K hero still - Ultra quality (Cycles)
echo  Estimated time on your PC: about 6-12 hours.
echo  The window shows progress after every frame. You can close it at any time:
echo  finished frames are kept and the next run continues where it stopped.
echo.
"%BLENDER%" -b "%~dp0project.blend" -P "%~dp0scripts\render.py" -- --preset ULTRA --engine CYCLES --still 1060
echo.
echo  Done! Opening the "renders" folder...
start "" "%~dp0renders"
pause
