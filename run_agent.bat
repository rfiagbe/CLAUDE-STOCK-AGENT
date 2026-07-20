@echo off
cd /d "%~dp0"
python stock_agent.py >> task_run.log 2>&1
