@echo off
REM Big_Agent All-in-One Script
REM Bu script kurulum ve çalıştırmayı otomatikleştirir

setlocal enabledelayedexpansion

echo.
echo ========================================
echo Big_Agent Kurulum ve Çalıştırma
echo ========================================
echo.

REM Python yolu (proje kokune gore, bu script'in bulundugu klasor)
set PROJECT_PATH=%~dp0
set PYTHON_PATH=%PROJECT_PATH%.venv\Scripts\python.exe

REM Python'un var olup olmadığını kontrol et
if not exist "!PYTHON_PATH!" (
    echo.
    echo [HATA] Python bulunamadı:
    echo !PYTHON_PATH!
    echo.
    pause
    exit /b 1
)

echo [OK] Python bulundu
echo.

REM requirements.txt'i yükle
echo Bağımlılıklar yükleniyor...
echo.
"!PYTHON_PATH!" -m pip install -r requirements.txt

if !errorlevel! neq 0 (
    echo.
    echo [HATA] Bağımlılıklar yüklenirken hata oluştu!
    pause
    exit /b 1
)

echo.
echo [OK] Bağımlılıklar başarıyla yüklendi!
echo.

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

echo ========================================
echo Uygulamayı Başlatıyor...
echo ========================================
echo.
echo Uygulamaya buradan erişebilirsiniz:
echo http://127.0.0.1:8000/
echo.
echo Uygulamayı durdurmak için Ctrl+C tuşlarına basın.
echo.

"!PYTHON_PATH!" -m uvicorn app.main:app --host 127.0.0.1 --port 8000

pause
