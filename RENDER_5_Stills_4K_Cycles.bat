@echo off
title Ten photoreal 4K stills - one per camera shot (Cycles)
cd /d "%~dp0"
call "%~dp0scripts\windows\find_blender.bat" || exit /b 1
echo.
echo  Ten photoreal 4K stills - one per camera shot (Cycles)
echo  Estimated time on your PC: about 30-60 minutes per image.
echo  The window shows progress after every frame. You can close it at any time:
echo  finished frames are kept and the next run continues where it stopped.
echo.
"%BLENDER%" -b "%~dp0project.blend" -P "%~dp0scripts\render.py" -- --preset HIGH --engine CYCLES --stills
echo.
echo  Done! Opening the "renders" folder...
start "" "%~dp0renders"
pause
