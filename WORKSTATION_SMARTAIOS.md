# SmartAIOS Workstation - SmartCAE AI

Bu belge, workstation üzerindeki `C:\SmartAIOS\Big_Agent` kurulumunu güncellemek ve SmartCAE AI uygulamasını çalıştırmak içindir.

## 1. Uygulamayı güncelleme

PowerShell'i açın:

```powershell
cd C:\SmartAIOS\Big_Agent
git status --porcelain
git branch --show-current
git fetch --prune origin
git pull --ff-only
```

`git status --porcelain` çıktı verirse güncellemeye devam etmeyin. `data`, `models` ve `.venv` klasörleri yereldir; silinmemeli ve Git'e eklenmemelidir.

## 2. SmartCAE AI'ı çalıştırma

```powershell
cd C:\SmartAIOS\Big_Agent

$env:APP_VARIANT = "big_agent"
$env:BIG_AGENT_DATA_DIR = "C:\SmartAIOS\Big_Agent\data"
$env:APP_AUTH_ENABLED = "false"
$env:APP_AUTH_COOKIE_NAME = "big_agent_session"

$env:EMBEDDING_PROVIDER = "sentence-transformers"
$env:EMBEDDING_MODEL_NAME = "C:\SmartAIOS\Big_Agent\models\Qwen3-Embedding-4B"
$env:EMBEDDING_LOCAL_FILES_ONLY = "true"
$env:EMBEDDING_DEVICE = "cuda"

& "C:\SmartAIOS\Big_Agent\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 0.0.0.0 --port 8002
```

Uygulamayı durdurmak için aynı PowerShell penceresinde `Ctrl+C` kullanın.

## 3. Uygulamayı açma

- Workstation: `http://localhost:8002/`
- Başka bilgisayar: `http://WORKSTATION_IP:8002/`
- Sağlık kontrolü: `http://localhost:8002/health`

## Sorun olursa

- Sayfa güncellenmediyse tarayıcıda `Ctrl+F5` yapın.
- Portu kontrol edin: `netstat -ano | findstr :8002`
- Ağdan erişilemiyorsa Windows Güvenlik Duvarı'nda TCP `8002` portuna izin verin.
- Model bulunamazsa `models\Qwen3-Embedding-4B` klasörünü ve Python yolu olarak `.venv\Scripts\python.exe` dosyasını kontrol edin.
