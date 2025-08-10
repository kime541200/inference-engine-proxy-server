使用 llama.cpp 的 `llama-server` 時，設定 `--metrics` 來啟用 Prometheus 格式監控指標，用於追蹤 **LLM 的效能狀況與當前佇列狀態**。

推論引擎啟動後，可以從 `/metrics` 取得，例如：
```bash
$ curl http://localhost:8080/metrics
# HELP llamacpp:prompt_tokens_total Number of prompt tokens processed.
# TYPE llamacpp:prompt_tokens_total counter
llamacpp:prompt_tokens_total 33065
# HELP llamacpp:prompt_seconds_total Prompt process time
# TYPE llamacpp:prompt_seconds_total counter
llamacpp:prompt_seconds_total 235.743
# HELP llamacpp:tokens_predicted_total Number of generation tokens processed.
# TYPE llamacpp:tokens_predicted_total counter
llamacpp:tokens_predicted_total 7801
# HELP llamacpp:tokens_predicted_seconds_total Predict process time
# TYPE llamacpp:tokens_predicted_seconds_total counter
llamacpp:tokens_predicted_seconds_total 279.178
# HELP llamacpp:n_decode_total Total number of llama_decode() calls
# TYPE llamacpp:n_decode_total counter
llamacpp:n_decode_total 7831
# HELP llamacpp:n_busy_slots_per_decode Average number of busy slots per llama_decode() call
# TYPE llamacpp:n_busy_slots_per_decode counter
llamacpp:n_busy_slots_per_decode 1
# HELP llamacpp:prompt_tokens_seconds Average prompt throughput in tokens/s.
# TYPE llamacpp:prompt_tokens_seconds gauge
llamacpp:prompt_tokens_seconds 140.259
# HELP llamacpp:predicted_tokens_seconds Average generation throughput in tokens/s.
# TYPE llamacpp:predicted_tokens_seconds gauge
llamacpp:predicted_tokens_seconds 27.9427
# HELP llamacpp:requests_processing Number of requests processing.
# TYPE llamacpp:requests_processing gauge
llamacpp:requests_processing 0
# HELP llamacpp:requests_deferred Number of requests deferred.
# TYPE llamacpp:requests_deferred gauge
llamacpp:requests_deferred 0
```

---

# 各個指標的詳細解釋

## 📊 累積計數器（counter）

這些指標會不斷累加，表示自伺服器啟動以來的總值。

### 1. `llamacpp:prompt_tokens_total`

> **說明**：總共處理過的 **Prompt tokens** 數量。
> **用途**：代表用戶輸入（prompt）部分的總 token 數，反映使用密集度。

➡️ **例如**：若使用者送出 3 次 prompt，各為 10、20、30 tokens，這個值會是 `60`。

---

### 2. `llamacpp:prompt_seconds_total`

> **說明**：處理 prompt tokens 總共花費的時間（秒）。
> **用途**：搭配上面 token 數量可估算平均 throughput。

---

### 3. `llamacpp:tokens_predicted_total`

> **說明**：總共產生（推論）出的 **output tokens** 數量。
> **用途**：代表模型實際生成的文字量。

---

### 4. `llamacpp:tokens_predicted_seconds_total`

> **說明**：用於推論 tokens 的總耗時。
> **用途**：可計算 **平均生成速率**，例如 tokens per second。

---

### 5. `llamacpp:n_decode_total`

> **說明**：呼叫 `llama_decode()` 的總次數。
> **用途**：代表模型解碼階段的計算次數，反映後端壓力與 token-by-token generation 行為。

---

### 6. `llamacpp:n_busy_slots_per_decode`

> **說明**：每次 decode 平均忙碌的 slot 數（所有 slot 是執行推論請求的 worker context）。
> **用途**：評估多任務併發程度或共享記憶區利用率。

> ⚠️ 雖然這是 counter，但表示的是「累積總和」，例如：decode 了 3 次，slot 忙碌數為 1, 2, 3，那這邊會是 `6`。

---

## ⚡ 即時數值（gauge）

這類指標會即時變動，反映當前瞬間的狀態。

### 7. `llamacpp:prompt_tokens_seconds`

> **說明**：**平均 prompt throughput**（tokens/sec）。
> **用途**：效能評估，可監控 prompt 輸入階段的處理速度。
> **計算式**：

```text
llamacpp:prompt_tokens_total / llamacpp:prompt_seconds_total
= 33065 / 235.743 ≈ 140.259
```

---

### 8. `llamacpp:predicted_tokens_seconds`

> **說明**：**平均生成 throughput**（tokens/sec）。
> **用途**：推論效能的關鍵指標，若數字下降可能代表伺服器過載或模型效能瓶頸。
> **計算式**：

```text
tokens_predicted_total / tokens_predicted_seconds_total
= 7801 / 279.178 ≈ 27.94
```

---

### 9. `llamacpp:requests_processing`

> **說明**：**當前正在處理的請求數**（例如正在 decoding）。
> **用途**：非常實用的動態負載指標，**可用來做 proxy 路由決策**。數值越高代表越忙。

---

### 10. `llamacpp:requests_deferred`

> **說明**：因資源不足、slot 滿載而被延後的請求數。
> **用途**：代表壓力瓶頸，若此數字非零，代表當下模型太忙導致排隊。
> **建議**：搭配 `requests_processing` 一起使用，建立閾值警示或負載移轉機制。

---

## 🔧 小結：實務應用建議

| 指標                                               | 實用情境    | 建議用途                |
| ------------------------------------------------ | ------- | ------------------- |
| `requests_processing`                            | 即時流量判斷  | proxy routing（挑最閒的） |
| `requests_deferred`                              | 壓力瓶頸    | 熔斷器、overload 保護     |
| `tokens_predicted_seconds`                       | 模型效能趨勢  | 預警 / 時間窗分析          |
| `prompt_tokens_total` + `tokens_predicted_total` | 使用量統計   | 計費、日誌記錄             |
| `n_busy_slots_per_decode`                        | 多任務併發觀察 | slot tuning 調參依據    |


---
---


# 延伸應用
- 計算 per minute 使用趨勢
- 當 `requests_deferred` 升高時自動降載
- 利用 Grafana 視覺化所有指標

---

## ✅ 1. 計算「每分鐘使用趨勢」

### 🎯 目標

從 `/metrics` 指標中推算「過去 1 分鐘的 tokens 處理量」或「推論 throughput」，例如：

* 每分鐘 prompt token 數
* 每分鐘生成 token 數
* 每分鐘平均 latency

### 🧠 原理

Prometheus 的 counter 是累積值（例如 `llamacpp:tokens_predicted_total`），但 Prometheus 本身支援對這類 counter 做時間差的查詢：

### 📌 Prometheus Query 寫法

```promql
rate(llamacpp:tokens_predicted_total[1m])
```

* `rate(...)`：計算每秒增量（滑動時間窗平均）。
* `[...]`：表示時間窗，例如 1 分鐘。
* 若想換成「每分鐘」token 數，可乘以 60：

```promql
rate(llamacpp:tokens_predicted_total[1m]) * 60
```

其他類似用法：

```promql
# 每分鐘 prompt token 數
rate(llamacpp:prompt_tokens_total[1m]) * 60

# 過去 5 分鐘 average throughput
avg(rate(llamacpp:tokens_predicted_total[5m]) * 60)
```

### 🧪 實作方式

只要把 llama-server `/metrics` 曝光給 Prometheus（下面第 3 點會說明），就可以直接在 Grafana 或 AlertManager 上設定每分鐘使用趨勢圖表與警示。

---

## 🚨 2. 當 `requests_deferred` 升高時自動降載（Overload 保護）

### 🎯 目標

當某一台 llama-server 太忙（佇列已滿）時，自動：

* 拒絕新請求
* 把請求路由到其他 backend
* 或回傳 503 錯誤（soft fail）

### 🧠 判斷條件

| 指標                        | 判斷意義             |
| ------------------------- | ---------------- |
| `requests_processing` ≥ N | 表示正在處理很多請求（負載高）  |
| `requests_deferred` > 0   | **代表模型已滿載，排不進去** |

### 🧰 Proxy 實作方式（簡化）

```py
# 過載保護條件
MAX_ALLOWED_DEFERRED = 2

# 在 fetch_metrics() 裡加入條件
if 'llamacpp:requests_deferred' in family.name:
    deferred = family.samples[0].value
    if deferred >= MAX_ALLOWED_DEFERRED:
        ready = False  # 即使 health OK，也排除
```

這樣就能讓 proxy「識別出過載節點」並自動略過。

### 🔁 更進一步：動態限流

你甚至可以設定在 deferred 上升時減少每台允許的 concurrent 請求數，做到 soft 限流，或在 Nginx 層級設定後端失敗重試。

---

## 📊 3. 使用 Grafana 視覺化 llama-server 指標

### 🧱 架構需求

你需要以下三個元件：

1. **Prometheus**：收集 `/metrics` 指標
2. **Grafana**：做視覺化儀表板
3. **llama-server**：已開啟 `--metrics`，並能被 Prometheus 抓取

### 📦 Prometheus 設定範例 `prometheus.yml`

```yaml
scrape_configs:
  - job_name: 'llamacpp'
    static_configs:
      - targets: ['llm-0:8080', 'llm-1:8080']
```

> 只要這些 targets 能抓到 `/metrics` 頁面（llama-server 有啟 `--metrics`），Prometheus 就會開始收資料。

你可以用 `docker-compose` 把 Prometheus 加入現有架構（我可幫你配置）。

---

### 📊 Grafana Dashboard 建議圖表

| 圖表                    | PromQL 查詢語法                                 | 說明       |
| --------------------- | ------------------------------------------- | -------- |
| Prompt Token 每秒       | `rate(llamacpp:prompt_tokens_total[1m])`    | 輸入量      |
| Generation Token 每秒   | `rate(llamacpp:tokens_predicted_total[1m])` | 輸出量      |
| Prompt throughput     | `llamacpp:prompt_tokens_seconds`            | 即時       |
| Generation throughput | `llamacpp:predicted_tokens_seconds`         | 即時       |
| Requests processing   | `llamacpp:requests_processing`              | 可做 alert |
| Requests deferred     | `llamacpp:requests_deferred`                | 過載指標     |

---

### 📌 範例圖示

你可以用「Stat」或「Time series」元件畫出：

* 每台 server 的 token throughput 趨勢
* Slot 使用率（busy slots）
* 過去 1 分鐘平均推論速率
* Deferred 警示閾值（紅色）

---

## ✅ 結語與建議

| 項目         | 建議工具                         | 備註                   |
| ---------- | ---------------------------- | -------------------- |
| 監控 + 圖表    | Prometheus + Grafana         | 最穩定且社群活躍             |
| Proxy 路由策略 | FastAPI + `/metrics` 快取      | 可加上 weighted routing |
| 警示通知       | Grafana Alert 或 AlertManager | 可接 Slack、Email       |
