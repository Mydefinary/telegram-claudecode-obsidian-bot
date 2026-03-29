@echo off
chcp 65001 >nul
title Telegram-Obsidian Bot
cd /d "%~dp0"
python bot.py
pause
