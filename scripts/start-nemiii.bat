@echo off
REM start-nemiii.bat — launches Nemiii inside WSL, then opens the browser.
REM
REM To run automatically when you log into Windows:
REM   1. Press Win+R, type: shell:startup, press Enter
REM   2. Right-click in that folder -> New -> Shortcut
REM   3. Point it at this file's full path
REM      (e.g. \\wsl$\Ubuntu\home\nemin\friday\nemin-ai-assist\scripts\start-nemiii.bat
REM       or wherever you saved a Windows-side copy)
REM
REM If Startup-folder timing feels unreliable (WSL not ready yet right after
REM login), use Task Scheduler instead: create a task triggered "At log on",
REM with a 20-30 second delay, running this same command.

wsl.exe bash -lc "~/friday/nemin-ai-assist/scripts/start-nemiii.sh"
