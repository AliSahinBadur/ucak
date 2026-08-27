@echo off
REM Big_Agent All-in-One Script (Generic)
REM Bu script kurulum ve calistirmayi otomatiklestirir
REM Makineye ozgu yol icermez; script nerede olursa oradan calisir.

setlocal enabledelayedexpansion

echo.
echo ========================================
echo Big_Agent Kurulum ve Calistirma
echo ========================================
echo.

REM Proje klasoru: bu script'in bulundugu klasor
set "PROJECT_PATH=%~dp0"
if "!PROJECT_PATH:~-1!"=="\" set "PROJECT_PATH=!PROJECT_PATH:~0,-1!"

REM Python'u bul: once yerel .venv, sonra PATH uzerindeki py/python
set "PYTHON_PATH="

if exist "!PROJECT_PATH!\.venv\Scripts\python.exe" (
    set "PYTHON_PATH=!PROJECT_PATH!\.venv\Scripts\python.exe"
) else (
    where py >nul 2>nul
    if !errorlevel! equ 0 (
        set "PYTHON_PATH=py"
    ) else (
        where python >nul 2>nul
        if !errorlevel! equ 0 (
            set "PYTHON_PATH=python"
        )
    )
)

if "!PYTHON_PATH!"=="" (
    echo.
    echo [HATA] Python bulunamadi. Lutfen Python'u kurun veya PATH'e ekleyin.
    echo.
    pause
    exit /b 1
)

echo [OK] Python bulundu: !PYTHON_PATH!
echo.

REM Proje klasorune git
cd /d "!PROJECT_PATH!"

if !errorlevel! neq 0 (
    echo.
    echo [HATA] Proje klasorune gidilemedi:
    echo !PROJECT_PATH!
    echo.
    pause
    exit /b 1
)

REM requirements.txt'i yukle: once uv, yoksa pip
where uv >nul 2>nul
if !errorlevel! equ 0 (
    echo uv bulundu, bagimliliklar uv ile yukleniyor...
    echo.
    uv pip install -r requirements.txt

    if !errorlevel! neq 0 (
        echo.
        echo [HATA] Bagimliliklar uv ile yuklenirken hata olustu!
        pause
        exit /b 1
    )

    echo.
    echo [OK] Bagimliliklar uv ile basariyla yuklendi!
    echo.
) else (
    echo uv bulunamadi, bagimliliklar pip ile yukleniyor...
    echo.
    "!PYTHON_PATH!" -m pip install -r requirements.txt

    if !errorlevel! neq 0 (
        echo.
        echo [HATA] Bagimliliklar pip ile yuklenirken hata olustu!
        pause
        exit /b 1
    )

    echo.
    echo [OK] Bagimliliklar pip ile basariyla yuklendi!
    echo.
)

echo ========================================
echo Uygulamayi Baslatiyor...
echo ========================================
echo.
echo Uygulamaya buradan erisebilirsiniz:
echo http://127.0.0.1:8000/
echo.
echo Uygulamayi durdurmak icin Ctrl+C tuslarina basin.
echo.

"!PYTHON_PATH!" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
