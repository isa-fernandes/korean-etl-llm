@echo off
setlocal

start "TOPIK Docs" http://127.0.0.1:8000/
python docs\serve_docs.py