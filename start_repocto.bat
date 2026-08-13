@echo off
call "%~dp0start_big_agent.bat" repocto 8004 full
exit /b %ERRORLEVEL%
