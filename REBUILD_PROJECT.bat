@echo off
title Rebuild The Clockmaker's Workshop from scripts
cd /d "%~dp0"
call "%~dp0scripts\windows\find_blender.bat" || exit /b 1
echo Regenerating audio...
"%BLENDER%" -b --factory-startup -P "%~dp0scripts\make_audio.py"
echo Rebuilding project.blend from the Python scripts...
"%BLENDER%" -b --factory-startup -P "%~dp0scripts\build_scene.py"
echo Done.
pause
