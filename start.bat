@echo off
REM Big_Agent All-in-One Script
REM Bu script kurulum ve çalıştırmayı otomatikleştirir

setlocal enabledelayedexpansion

echo.
echo ========================================
echo Big_Agent Kurulum ve Çalıştırma
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
