@echo off
title Film - 4K UHD, EEVEE (highest resolution film)
cd /d "%~dp0"
call "%~dp0scripts\windows\find_blender.bat" || exit /b 1
echo.
echo  Film - 4K UHD, EEVEE (highest resolution film)
echo  Estimated time on your PC: about 12-24 hours (good to run overnight).
echo  The window shows progress after every frame. You can close it at any time:
echo  finished frames are kept and the next run continues where it stopped.
echo.
"%BLENDER%" -b "%~dp0project.blend" -P "%~dp0scripts\render.py" -- --preset HIGH --engine EEVEE --encode
echo.
echo  Done! Opening the "renders" folder...
start "" "%~dp0renders"
pause
