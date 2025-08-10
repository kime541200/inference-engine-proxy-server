# Inference Engine Proxy Server

這是一個高效能、高可用的推論引擎代理伺服器，旨在作為多個後端大型語言模型（LLM）推論引擎的統一入口。它能智慧地將傳入的請求轉發到當下最空閒的後端服務，實現自動負載平衡與故障轉移，並支援流式回應。

目前已完整支援 `llama.cpp`，並已為未來擴充支援 `vLLM` 等其他引擎打好基礎。

---

## 核心功能

- **動態負載平衡 (Dynamic Load Balancing)**：根據後端引擎的即時指標（如處理中請求數、等待中請求數），自動選擇最空閒的服務來處理新請求。
- **背景健康檢查 (Background Health Checks)**：透過非阻塞的背景任務，定期檢查所有後端服務的健康狀況與負載，決策過程對使用者請求零延遲。
- **統一的 API 入口 (Centralized Entry Point)**：使用者只需訪問本代理伺服器的單一端口，無需關心後端有多少台服務以及它們的實際位址。
- **完整的流式支援 (Full Streaming Support)**：從請求接收到後端轉發，再到回應給客戶端，全程支援流式處理，確保 LLM 的 token 可以即時傳遞。
- **完全離線運行 (Fully Offline Operation)**：在模型和 Docker 鏡像都已本地化的情況下，整個服務堆疊無需網際網路連線即可運行，確保資料的私密性與安全性。
- **可擴充的後端架構 (Extensible Architecture)**：透過抽象基礎類別（ABC）設計，可以輕鬆擴充以支援 `vLLM` 等不同類型的推論引擎。
- **容器化部署 (Containerized)**：整個專案（包含代理伺服器、後端引擎、NGINX）都透過 Docker 和 Docker Compose 進行管理，方便一鍵啟動與部署。

---

## 架構圖

專案採用了分層的代理架構，以實現認證、負載平衡與服務的解耦。

```
          (外部)           (Docker 內部網路)
┌───────┐ 8888 ┌─────────┐ 8888  ┌──────────┐ 8080  ┌──────────┐
│Client │ ───▶ │ NGINX   │ ───▶ │ Proxy     │ ───▶ │ llama-1  │
└───────┘      │ (認證層)│      │ (FastAPI) │      │          │
               └─────────┘      └──────────┘      └──────────┘
                               │                  ┌──────────┐
                               └─────────────────▶│ llama-2  │
                                                  └──────────┘
```

---

## 技術棧

- **Proxy Server**: Python 3.12, FastAPI
- **HTTP Client**: HTTPX (for async requests & connection pooling)
- **Web Server/Gateway**: Uvicorn, NGINX
- **容器化**: Docker, Docker Compose
- **後端引擎**: `[llama.cpp](https://github.com/ggml-org/llama.cpp.git)`、`[vllm](https://github.com/vllm-project/vllm)` (OpenAI-compatible API)

---

## 安裝與啟動

請確保您的系統已安裝 `Docker`、`Docker Compose` 以及 `NVIDIA Container Toolkit`（若需使用 GPU）。

#### 1. 準備推論引擎鏡像

請預先下載您需要的推論引擎官方 Docker 鏡像：
- [llama.cpp 官方 Docker 鏡像](https://github.com/ggml-org/llama.cpp/pkgs/container/llama.cpp)
- [vllm 官方 Docker 鏡像](https://hub.docker.com/r/vllm/vllm-openai/tags)

```bash
# 範例：拉取 llama.cpp 的 CUDA 版本鏡像
docker pull ghcr.io/ggml-org/llama.cpp:server-cuda-b6107
```

#### 2. 建立外部網路

由於 `docker-compose.llamacpp.yml` 使用了外部網路，您需要先手動建立它：
```bash
docker network create dev
```

#### 3. 設定環境變數

將專案根目錄下的 `.env.example` 檔案複製一份並命名為 `.env`。

```bash
cp .env.example .env
```

接著，根據您的環境修改 `.env` 檔案的內容。

**.env.example**
```env
# Proxy Server 監聽的外部端口
PORT=8888

# GGUF 模型檔案所在的目錄與檔名
MODEL_DIR=/path/to/your/models
MODEL=your-model-q4_0.gguf

# 後端服務的 URL，必須與 docker-compose.yml 中的服務名稱對應
BACKENDS=http://llm-1:8080,http://llm-2:8080

# 背景指標快取的更新頻率（秒）
METRICS_CACHE_TTL_SECONDS=3

# 請求後端的超時時間（秒）
BACKEND_TIMEOUT_SECONDS=300

# 後端引擎的能力上限，用於健康檢查判斷
MAX_ALLOWED_REQUEST_QUEUE=6
MAX_ALLOWED_DEFERRED=3
```
**注意**: `MODEL_DIR` 請務必修改為您在主機上存放模型的真實路徑。

#### 4. 啟動服務

使用 Docker Compose 一鍵啟動所有服務（包括 NGINX、Proxy 和兩個 llama.cpp 實例）：

```bash
# -f 指定設定檔
# --build 首次啟動時或程式碼變更後，強制重建 proxy 鏡像
# -d 在背景執行
docker compose -f docker-compose.llamacpp.yml up --build -d
```

#### 5. 驗證狀態

- **檢查容器狀態**:
  ```bash
  docker compose -f docker-compose.llamacpp.yml ps
  ```
- **查看日誌**:
  ```bash
  docker compose -f docker-compose.llamacpp.yml logs -f proxy
  ```
- **訪問健康檢查端點**:
  ```bash
  curl http://localhost:8888/health
  ```
  如果一切正常，您會看到類似以下的 JSON 回應：
  ```json
  {
    "status": "ok",
    "available_backends": [
      "http://llm-1:8080",
      "http://llm-2:8080"
    ],
    "total_backends": 2,
    "timestamp": 1723181235.123,
    "details": [
        ...
    ]
  }
  ```

---

## API 使用方式

本代理伺服器會將所有 `/{full_path:path}` 的請求透明地轉發到後端。您可以像直接請求 `llama.cpp` 的 OpenAI 相容 API 一樣來使用它。

**範例：發起一個聊天請求**

```bash
curl http://localhost:8888/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "your-model-q4_0.gguf",
    "messages": [
      {
        "role": "system",
        "content": "You are a helpful assistant."
      },
      {
        "role": "user",
        "content": "你好，請介紹一下台灣雲林縣。"
      }
    ],
    "stream": true
  }'
```

---

## 客製化推論引擎

本專案的設計允許使用者高度自訂後端的推論服務。

### 更換 Docker 鏡像

您可以輕易更換 `llm-1` 和 `llm-2` 服務所使用的 Docker 鏡像。只需在 `docker-compose.llamacpp.yml` 檔案中，修改對應服務的 `image` 欄位即可。

例如，若您想使用一個特定版本的 `vllm` 鏡像，可以這樣修改：
```yaml
services:
  llm-1:
    # image: ghcr.io/ggml-org/llama.cpp:server-cuda-b6107
    image: vllm/vllm-openai:v0.5.1 # <-- 修改為您需要的鏡像
    ...
```

### 調整啟動參數

所有推論引擎（如 `llama-server`）的啟動參數都定義在 `docker-compose.llamacpp.yml` 的 `command` 區塊中。您可以根據官方文件自由修改這些參數，以調整模型的行為或效能。

例如，您可以修改上下文長度 (`-c`)、GPU offload 層數 (`-ngl`)、溫度 (`--temp`) 等。
```yaml
services:
  llm-1:
    ...
    command: >
      ./llama-server
      -m ${MODEL_DIR}/${MODEL}
      -c 8192              # <-- 修改上下文長度
      -ngl 99
      --temp 0.2           # <-- 修改溫度參數
      ...
```

---

## 未來計畫

- [ ] 完成 `VllmBackend` 的實作，以完整支援 vLLM 推論引擎。
- [ ] 在 NGINX 層增加更豐富的認證機制（如 API Key, JWT）。
- [ ] 增加更詳細的 Prometheus 指標，以便監控代理伺服器本身的效能。

---

## 授權 (License)

本專案採用 [MIT License](LICENSE) 授權。