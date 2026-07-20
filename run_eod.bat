@echo off
cd /d "%~dp0"
python eod_update.py >> task_run.log 2>&1
