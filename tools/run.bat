@echo off
rem Scheduled task entry: pull latest code, then run trendbot. Logs go to data\logs\run.log
cd /d %~dp0\..
if not exist data\logs mkdir data\logs
git pull --quiet >> data\logs\run.log 2>&1
call .venv\Scripts\activate.bat
python -m trendbot %* >> data\logs\run.log 2>&1
