@echo off
rem roBa キー配置オーバーレイを起動（黒い画面は出さずに裏で動く）
rem 終了は Ctrl + Alt + Q
cd /d "%~dp0"
where pyw >nul 2>nul
if %errorlevel%==0 (
    start "" pyw "%~dp0roba_overlay.py" %*
    exit /b
)
where pythonw >nul 2>nul
if %errorlevel%==0 (
    start "" pythonw "%~dp0roba_overlay.py" %*
    exit /b
)
echo Python が見つかりません。https://www.python.org/downloads/ からインストールしてください。
echo （インストール時に「Add python.exe to PATH」にチェック）
pause
