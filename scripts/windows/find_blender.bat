@echo off
rem Locates blender.exe and stores it in %BLENDER%.
rem If Blender is installed somewhere unusual, set the full path on the next line, e.g.
rem set "BLENDER=D:\Apps\Blender 5.2\blender.exe"
set "BLENDER="
for /d %%D in ("%ProgramFiles%\Blender Foundation\Blender*") do if exist "%%D\blender.exe" set "BLENDER=%%D\blender.exe"
if not defined BLENDER if exist "%ProgramFiles(x86)%\Steam\steamapps\common\Blender\blender.exe" set "BLENDER=%ProgramFiles(x86)%\Steam\steamapps\common\Blender\blender.exe"
if not defined BLENDER for /d %%D in ("%LOCALAPPDATA%\Programs\Blender Foundation\Blender*") do if exist "%%D\blender.exe" set "BLENDER=%%D\blender.exe"
if not defined BLENDER (where blender >nul 2>nul && set "BLENDER=blender")
if not defined BLENDER (
  echo.
  echo  Blender was not found. Please install Blender 5.2 from https://www.blender.org/download/
  echo  then run this file again.
  echo.
  pause
  exit /b 1
)
echo Using Blender: "%BLENDER%"
exit /b 0
