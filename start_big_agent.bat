@echo off
setlocal

set "APP_DIR=%~dp0"
set "VENV_DIR=%APP_DIR%.venv"
set "PYTHON_EXE=%VENV_DIR%\Scripts\python.exe"
set "PYTHON_INSTALLER="
set "PYTORCH_VERSION=2.6.0"
set "PYTORCH_CUDA_INDEX=https://download.pytorch.org/whl/cu124"
set "EMBEDDING_DEVICE=cuda"
set "APP_VARIANT=big_agent"
set "PORT=8002"
set "RUN_MODE=full"

if not "%~1"=="" set "APP_VARIANT=%~1"
if not "%~2"=="" set "PORT=%~2"
if not "%~3"=="" set "RUN_MODE=%~3"

if /I "%APP_VARIANT%"=="big_agent" (
  set "APP_NAME=SmartCAE AI"
  set "BIG_AGENT_DATA_DIR=%APP_DIR%data"
  set "APP_AUTH_COOKIE_NAME=big_agent_session"
) else if /I "%APP_VARIANT%"=="raporhub" (
  set "APP_NAME=ReportHub"
  set "RAPORHUB_DATA_DIR=%APP_DIR%data_raporhub"
  set "APP_AUTH_COOKIE_NAME=raporhub_session"
) else if /I "%APP_VARIANT%"=="repocto" (
  set "APP_NAME=RepOcto"
  set "RAPORHUB_DATA_DIR=%APP_DIR%data_raporhub"
  set "APP_AUTH_COOKIE_NAME=repocto_session"
) else (
  echo [HATA] Bilinmeyen uygulama varyanti: %APP_VARIANT%
  echo Desteklenen degerler: big_agent, raporhub, repocto
  pause
  exit /b 1
)

echo.
echo ========================================
echo %APP_NAME% kurulum ve baslatma
echo Klasor: %APP_DIR%
echo Port: %PORT%
echo Varyant: %APP_VARIANT%
echo Mod: %RUN_MODE%
echo ========================================
echo.

if /I "%RUN_MODE%"=="run-only" goto :runtime_ready

where python >nul 2>nul
if errorlevel 1 (
  echo [BILGI] Python bulunamadi. Klasorde Python installer araniyor...
  for %%F in ("%APP_DIR%python-3.12*.exe" "%APP_DIR%python-3.11*.exe" "%APP_DIR%installers\python-3.12*.exe" "%APP_DIR%installers\python-3.11*.exe") do (
    if exist "%%~fF" (
      set "PYTHON_INSTALLER=%%~fF"
      goto :python_installer_found
    )
  )

  echo [HATA] Python bulunamadi ve installer dosyasi yok.
  echo Big_Agent klasorune python-3.12.x-amd64.exe dosyasini koyup tekrar deneyin.
  pause
  exit /b 1
)
goto :python_ready

:python_installer_found
echo [BILGI] Python installer bulundu:
echo %PYTHON_INSTALLER%
echo [BILGI] Kullanici bazli sessiz Python kurulumu deneniyor...
"%PYTHON_INSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_test=0 Include_launcher=1
if errorlevel 1 (
  echo [HATA] Python kurulumu basarisiz. Manuel kurulum gerekebilir.
  pause
  exit /b 1
)
echo [BILGI] Python kurulumu tamamlandi. PATH yenileniyor...
set "PATH=%LOCALAPPDATA%\Programs\Python\Python312;%LOCALAPPDATA%\Programs\Python\Python312\Scripts;%LOCALAPPDATA%\Programs\Python\Python311;%LOCALAPPDATA%\Programs\Python\Python311\Scripts;%PATH%"
where python >nul 2>nul
if errorlevel 1 (
  echo [HATA] Python kuruldu ancak bu oturumda bulunamadi. PowerShell/CMD kapatip tekrar deneyin.
  pause
  exit /b 1
)

:python_ready
set "NVIDIA_SMI=nvidia-smi"
where nvidia-smi >nul 2>nul
if errorlevel 1 (
  if exist "%ProgramFiles%\NVIDIA Corporation\NVSMI\nvidia-smi.exe" (
    set "NVIDIA_SMI=%ProgramFiles%\NVIDIA Corporation\NVSMI\nvidia-smi.exe"
  ) else (
    echo [HATA] NVIDIA surucusu veya nvidia-smi bulunamadi.
    echo Workstation NVIDIA surucusunu kurup batch dosyasini yeniden calistirin.
    pause
    exit /b 1
  )
)

echo [BILGI] NVIDIA GPU kontrol ediliyor...
"%NVIDIA_SMI%" --query-gpu=name,driver_version,memory.total --format=csv,noheader
if errorlevel 1 (
  echo [HATA] NVIDIA GPU bilgisi okunamadi.
  pause
  exit /b 1
)

if not exist "%PYTHON_EXE%" goto :create_venv
"%PYTHON_EXE%" -c "import sys" >nul 2>nul
if errorlevel 1 goto :recreate_venv
echo [1/6] Sanal ortam mevcut ve gecerli.
goto :venv_ready

:recreate_venv
echo [1/6] Tasinmis veya bozuk sanal ortam yeniden olusturuluyor...
python -m venv --clear "%VENV_DIR%"
if errorlevel 1 (
  echo [HATA] Sanal ortam yeniden olusturulamadi.
  pause
  exit /b 1
)
goto :venv_ready

:create_venv
echo [1/6] Sanal ortam olusturuluyor...
python -m venv "%VENV_DIR%"
if errorlevel 1 (
  echo [HATA] Sanal ortam olusturulamadi.
  pause
  exit /b 1
)

:venv_ready
echo [2/6] pip guncelleniyor...
"%PYTHON_EXE%" -m pip install --upgrade pip
if errorlevel 1 (
  echo [HATA] pip guncellenemedi.
  pause
  exit /b 1
)

if not exist "%APP_DIR%requirements.txt" (
  echo [HATA] requirements.txt bulunamadi: %APP_DIR%requirements.txt
  pause
  exit /b 1
)

echo [3/6] requirements.txt paketleri yukleniyor...
"%PYTHON_EXE%" -m pip install -r "%APP_DIR%requirements.txt"
if errorlevel 1 (
  echo [HATA] Temel paket kurulumu basarisiz.
  pause
  exit /b 1
)

if exist "%APP_DIR%requirements-skill.txt" (
  echo [3/6] Opsiyonel skill paketleri yukleniyor...
  "%PYTHON_EXE%" -m pip install -r "%APP_DIR%requirements-skill.txt"
  if errorlevel 1 (
    echo [HATA] Skill paket kurulumu basarisiz.
    pause
    exit /b 1
  )
)

echo [4/6] CUDA destekli PyTorch kontrol ediliyor...
"%PYTHON_EXE%" -c "import sys, torch; sys.exit(0 if torch.version.cuda and torch.cuda.is_available() else 1)" >nul 2>nul
if errorlevel 1 (
  echo [BILGI] CUDA destekli PyTorch %PYTORCH_VERSION% kuruluyor. Bu indirme uzun surebilir...
  "%PYTHON_EXE%" -m pip install --force-reinstall "torch==%PYTORCH_VERSION%" --index-url "%PYTORCH_CUDA_INDEX%"
  if errorlevel 1 (
    echo [HATA] CUDA destekli PyTorch kurulumu basarisiz.
    echo NVIDIA surucusunu ve internet erisimini kontrol edin.
    pause
    exit /b 1
  )
) else (
  echo [BILGI] CUDA destekli PyTorch zaten hazir.
)

"%PYTHON_EXE%" -c "import sys, torch; print('[BILGI] torch=' + torch.__version__); print('[BILGI] CUDA=' + str(torch.version.cuda)); print('[BILGI] GPU=' + (torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'YOK')); sys.exit(0 if torch.cuda.is_available() else 1)"
if errorlevel 1 (
  echo [HATA] PyTorch kuruldu ancak CUDA kullanilamiyor.
  echo Uygulama CPU modunda baslatilmadi. Workstation surucusunu kontrol edin.
  pause
  exit /b 1
)

if not exist "%APP_DIR%requirements-embeddings.txt" (
  echo [HATA] requirements-embeddings.txt bulunamadi: %APP_DIR%requirements-embeddings.txt
  pause
  exit /b 1
)

echo [5/6] Embedding paketleri yukleniyor...
"%PYTHON_EXE%" -m pip install -r "%APP_DIR%requirements-embeddings.txt"
if errorlevel 1 (
  echo [HATA] Embedding paket kurulumu basarisiz.
  pause
  exit /b 1
)

"%PYTHON_EXE%" -c "import sentence_transformers; print('[BILGI] sentence-transformers kurulumu dogrulandi.')"
if errorlevel 1 (
  echo [HATA] Embedding paketleri kuruldu ancak sentence-transformers yuklenemedi.
  pause
  exit /b 1
)

:runtime_ready
if not exist "%PYTHON_EXE%" (
  echo [HATA] Sanal ortam bulunamadi: %PYTHON_EXE%
  echo Once bu dosyayi normal modda veya setup-only modunda calistirin.
  pause
  exit /b 1
)

if not exist "%APP_DIR%.env" (
  if exist "%APP_DIR%.env.example" (
    echo [BILGI] .env bulunamadi. .env.example dosyasindan .env olusturuluyor.
    copy "%APP_DIR%.env.example" "%APP_DIR%.env" >nul
  )
)

if /I "%RUN_MODE%"=="setup-only" (
  echo.
  echo [BILGI] SmartCAE AI / ReportHub ortak ortami hazir.
  exit /b 0
)

echo [6/6] %APP_NAME% GPU modunda baslatiliyor...
echo.
echo Dinleme: 0.0.0.0:%PORT%
echo Yerel adres: http://127.0.0.1:%PORT%
echo Ag adresi: http://%COMPUTERNAME%:%PORT%
echo Embedding cihazi: %EMBEDDING_DEVICE%
echo Durdurmak icin bu pencerede CTRL+C kullan.
echo.

"%PYTHON_EXE%" -m uvicorn app.main:app --app-dir "%APP_DIR%" --host 0.0.0.0 --port %PORT%

echo.
echo Uygulama kapandi.
pause
