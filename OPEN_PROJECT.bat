@echo off
title Opening The Clockmaker's Workshop
cd /d "%~dp0"
call "%~dp0scripts\windows\find_blender.bat" || exit /b 1
rem --enable-autoexec lets the Director panel load automatically for this project
start "" "%BLENDER%" --enable-autoexec "%~dp0project.blend"
