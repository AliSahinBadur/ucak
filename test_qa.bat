@echo off
REM Big_Agent QA Test Script
REM Bu script QA/search regresyon testi yapar

setlocal enabledelayedexpansion

echo.
echo ========================================
echo Big_Agent QA/Search Regresyon Testi
echo ========================================
echo.

REM Python yolu
set PYTHON_PATH=C:\Users\ISU34977\PyCharmMiscProject\.venv\Scripts\python.exe
set PROJECT_PATH=C:\Users\ISU34977\PyCharmMiscProject\Big_Agent

REM Python'un var olup olmadığını kontrol et
if not exist "!PYTHON_PATH!" (
    echo.
    echo [HATA] Python bulunamadı:
    echo !PYTHON_PATH!
    echo.
    pause
    exit /b 1
)

REM Proje klasörüne git
cd /d "!PROJECT_PATH!"

if !errorlevel! neq 0 (
    echo.
    echo [HATA] Proje klasörüne gidilemedi:
    echo !PROJECT_PATH!
    echo.
    pause
    exit /b 1
)

echo [OK] Python bulundu
echo [OK] Proje klasörü açıldı
echo.

REM QA test'ini çalıştır
echo QA/Search regresyon testi çalıştırılıyor...
echo Beklenen sonuç: 22 passed, 0 failed
echo.

"!PYTHON_PATH!" scripts\run_qa_checks.py

if !errorlevel! neq 0 (
    echo.
    echo [HATA] QA test başarısız oldu!
    echo.
    pause
    exit /b 1
)

echo.
echo [OK] QA test tamamlandı!
echo.
pause
