# Benchmark & Observability Report — Day 14

> Mọi con số lấy từ report JSON trong `reports/`. Mục 4–6 thuộc Part 7 Bước 2 (Docker stack), **chưa làm**.

**Họ tên:** NguyenVietHoang
**Ngày chạy:** 2026-11-26 (Part 7 Bước 1)
**Môi trường:** Windows 11, Intel i5-13420H (12 luồng), RAM 15.7 GB, Python 3.12.10. Agent chạy trực tiếp trên máy (1 process uvicorn), máy tạo tải cũng là máy này. Gọi qua `127.0.0.1` để tránh độ trễ khi Windows thử IPv6 trước với `localhost`. Đặt `PYTHONUTF8=1` để script đọc và ghi JSON bằng UTF-8.

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Trùng ngưỡng mặc định của `load_test.py`. Khi chạy với concurrency 1–50, p95 đo được là 246–426 ms, nên ngưỡng này còn khoảng dự phòng nhưng vẫn bắt được lúc quá tải (c=100: 1274.6 ms) |
| Error rate `/ask` | < 2 % | Mock LLM mặc định lỗi khoảng 1% (`MOCK_ERROR_RATE=0.01`). Ngưỡng 2% chấp nhận mức nền này và báo khi lỗi tăng gấp đôi |
| Accuracy trên golden dataset | ≥ 90 % | Với 23 câu, được sai tối đa 2 câu. v2 ban đầu đạt 91.3% (qua), v1 đạt 4.3% (không qua) |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.97 | 202.7 | 245.8 | 1708.7 | 0.33% | ✅ PASS |
| 10 | 33.77 | 201.4 | 248.1 | 1715.0 | 1.00% | ✅ PASS |
| 50 | 95.15 | 238.2 | 426.1 | 1800.1 | 0.67% | ✅ PASS |
| 100 | 81.71 | 465.7 | 1274.6 | 2004.3 | 0.00% | ❌ FAIL (p95) |

Mỗi mức 300 request. Mọi request lỗi trong các lần chạy này là 503.

**Nhận xét:** RPS **không tăng tuyến tính**.
- **1 → 10:** RPS tăng 3.97 → 33.77 (khoảng 8.5 lần), p50 gần như không đổi. Hệ thống còn dư sức; thời gian chủ yếu là mock LLM chờ (async).
- **10 → 50:** concurrency tăng 5 lần nhưng RPS chỉ tăng khoảng 2.8 lần, p95 tăng 248 → 426 ms.
- **50 → 100:** RPS **giảm** 95.15 → 81.71, p50 gần gấp đôi, p95 vượt SLO. Tăng thêm tải chỉ làm request chờ lâu hơn.
- **Giải thích khả dĩ (chưa profile để xác nhận):** agent chỉ có một process và một event loop. Phần xử lý tốn CPU (middleware, ghi log JSON, parse request) phải xếp hàng, và máy tạo tải cũng dùng chung CPU.
- **Giới hạn của phép đo:** mỗi mức chỉ chạy một lần với 300 request. Ở c=50 và c=100 mỗi lần chỉ kéo dài hơn 3 giây, nên số RPS có thể dao động giữa các lần chạy.
- p99 khoảng 1.7 giây ngay cả khi c=1, do mock cố ý làm chậm khoảng 3% request (cộng thêm 1500 ms).

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 198.4 | 235.7 | 247.4 |
| 0.03 (mặc định) | 231.1 | 254.0 | 1705.3 |
| 0.1 | 338.8 | 1693.3 | 1727.1 |

Mỗi lần 300 request, concurrency 20. p50 gần như không đổi: 197.4 / 199.8 / 200.9 ms. Latency chỉ tính request trả 200.

**Nhận xét:**
- **p99 nhạy nhất.** Chỉ cần 3% request chậm, p99 tăng 247.4 → 1705.3 ms, trong khi avg chỉ tăng 32.7 ms và p95 tăng 18.3 ms.
- **p95 chỉ nhảy khi tỉ lệ chậm vượt khoảng 5%.** Ở mức 3%, request chậm nằm trong 5% trên cùng nên p95 chưa thấy. Ở mức 10%, p95 lên 1693.3 ms.
- **Không nên đặt SLO theo average.** Ở mức 10%, avg mới là 338.8 ms (vẫn dưới 500 ms) trong khi hơn 5% request mất khoảng 1.7 giây. SLO theo avg sẽ báo đạt, còn SLO p95 báo vi phạm.
- SLO chỉ theo p95 sẽ không thấy trường hợp 3%. Nếu cần bảo vệ nhóm này thì thêm SLO p99.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 57.7 | 109.1 | 114.2 |
| Tổng cost (USD) | 0.000412 | 0.000762 | 0.000795 |
| Cost / câu đúng (USD) | 0.00041175 | 0.00003627 | 0.00003458 |
| Quality gate | FAIL (≥ 80%) | PASS (≥ 80%) | PASS (≥ 100%, 0 regression so với v2) |
| Latency p50 / p95 (ms) | 173.2 / 188.6 | 204.5 / 244.2 | 206.0 / 234.8 |

**Những câu v2 trả lời sai ban đầu và cách sửa:**

| ID | Keyword bị thiếu | Đã sửa gì |
|---|---|---|
| `security-02` | token, hết hạn, chữ ký | Knowledge base không có tài liệu về JWT nên agent trả câu chung chung. Thêm tài liệu so sánh API key và JWT, từ khoá `jwt` |
| `scaling-03` | cpu, memory, custom metrics | Không có tài liệu về Kubernetes HPA. Thêm tài liệu, từ khoá `hpa`, `kubernetes`, `autoscal` |

Chỉ sửa `develop/utils/mock_llm.py`, không sửa golden dataset. Eval chấm theo keyword, nên 100% chỉ cho biết câu trả lời có đủ từ khoá trên 23 câu này, không chứng minh agent trả lời đúng với câu hỏi mới.

**Trade-off giữa v1 và v2:**
- **Chất lượng:** accuracy tăng từ 4.3% lên 91.3%.
- **Chi phí:** token mỗi câu gấp khoảng 1.9 lần và tổng cost gấp khoảng 1.85 lần, vì prompt có thêm context. Nhưng **cost cho mỗi câu đúng rẻ hơn khoảng 11 lần**. Chỉ nhìn cost mỗi câu thì v1 có vẻ rẻ, dù gần như không trả lời đúng.
- **Latency:** p50 tăng khoảng 31 ms do có bước retrieval và prompt dài hơn. p95 của eval chỉ tính trên 23 mẫu nên không dùng để kết luận; trong lần chạy v2 có một câu mất 1682 ms do request chậm ngẫu nhiên.

**Quality gate trong CI:** job ở `.github/workflows/eval.yml` chạy agent v2 rồi chạy `run_eval.py --min-accuracy 0.85` khi có pull request. Script trả **exit code 1** khi accuracy dưới ngưỡng, nên bước đó fail và job fail. Muốn GitHub **chặn merge**, phải bật branch protection cho `main` và đặt check `eval` là bắt buộc.
- Đã kiểm tra tại máy: với cùng ngưỡng 85%, agent v1 cho exit code 1. Lần chạy v2 sau khi sửa cho exit code 0 (với ngưỡng 100%).
- Job **chưa được chạy trên GitHub Actions** và branch protection chưa được bật.
- Job chưa dùng `--baseline`, nên chỉ chặn theo ngưỡng accuracy, không chặn riêng regression.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

Chọn request có `llm_ms` lớn nhất trong log 5 phút gần nhất, rồi mở trace cùng `trace_id` trong Jaeger ([ảnh](screenshots/jaeger-slow-trace.png)).

- `trace_id`: `8ec3f26acef87679756ed5f2878b0f9f`
- Tổng thời gian: 1763.4 ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (1740.1 ms, 98.7%). `agent.retrieve_context` chỉ mất 19.3 ms. Chậm là do lời gọi LLM, không phải retrieval hay phần còn lại của agent.
- Dòng log tương ứng:

```json
{"ts": "2026-11-26T16:37:12.994276+00:00", "level": "INFO", "service": "observable-agent", "instance": "60aac02faf72", "event": "llm_call", "trace_id": "8ec3f26acef87679756ed5f2878b0f9f", "span_id": "c4ebd6a32f5d0baa", "request_id": "808a63c8bef2", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 81, "output_tokens": 46, "cost_usd": 4e-05, "llm_ms": 1696.0}
```

**Trace lỗi** ([ảnh](screenshots/jaeger-error-trace.png)): `trace_id` `d13fba9b221cb037d73fe86527922a36`, tổng 95.2 ms, trả 503. Span `chat mock-llm-small` (74.0 ms) có `error.type=upstream_unavailable` và event `exception` (`utils.mock_llm.LLMError`). Dòng log cùng `trace_id`:

```json
{"ts": "2026-11-26T16:37:12.440633+00:00", "level": "INFO", "service": "observable-agent", "instance": "60aac02faf72", "event": "llm_error", "trace_id": "d13fba9b221cb037d73fe86527922a36", "span_id": "e4bb97b9f3273819", "request_id": "3b2ecccf4d17", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

Nhận xét thêm: dòng `llm_error` vẫn ghi `"level": "INFO"`, vì `log_event` gán cứng mức này. Lọc log theo mức ERROR sẽ bỏ sót lỗi.

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 59.67 | 200 | 360 | 1700 | 69/7126 (0.97%) |
| 3 | 59.31 | 190 | 240 | 1700 | 63/7089 (0.89%) |

Số lấy từ hàng `/ask` trong [scale_1_stats.csv](benchmark-results/scale_1_stats.csv) và [scale_3_stats.csv](benchmark-results/scale_3_stats.csv). Locust thoát với exit code 1 vì có request lỗi; báo cáo lỗi của Locust chỉ có mã 503. Mỗi cấu hình chạy một lần, lúc chạy đã đếm đúng 1 và 3 container agent.

**Giải thích kết quả:**
- **p95 cải thiện** từ 360 xuống 240 ms. p50 gần như không đổi.
- **RPS gần như bằng nhau.** Locust mô phỏng 100 user, mỗi user chờ phản hồi rồi nghỉ 0.5–2 giây, nên số request bị giới hạn bởi phía tạo tải. Phép thử này không cho biết thông lượng tối đa của 1 hay 3 instance.
- **p99 không đổi (1700 ms).** Đuôi chậm do mock LLM cố ý làm chậm khoảng 3% request. Thêm instance không làm một lời gọi LLM nhanh hơn. p95 của riêng LLM đo giữa lần chạy là khoảng 198 ms ở cả hai cấu hình.
- **Vì sao 1 instance có p95 cao hơn (giả thuyết, chưa kiểm chứng):** mỗi container bị giới hạn 0.5 CPU, nên khi một container nhận toàn bộ tải thì request có thể phải chờ CPU. Một lần đo `docker stats` ở giữa bài cho 25% với 1 instance, và 8–14% mỗi container với 3 instance. Một mẫu đơn lẻ không đủ để kết luận.

**Lỗi tìm thấy khi dựng stack:** `production/Dockerfile` ban đầu làm agent khởi động lại liên tục với lỗi `ModuleNotFoundError: No module named 'uvicorn'`. User `agent` có HOME là `/app`, còn thư viện nằm ở `/home/agent/.local`. Đã sửa bằng `ENV PYTHONUSERBASE=/home/agent/.local`. Lần benchmark trước khi sửa (100% mã 502) đã bị xoá, không dùng trong báo cáo.

---

## Phụ lục: Exercise 7.4 (đọc dashboard)

Tải: Locust 30 user, 2 instance. Số truy vấn từ Prometheus lúc 23:37:36 (cửa sổ 1 phút). [Ảnh dashboard](screenshots/grafana-dashboard.png) chụp khoảng 1 phút sau, nên số trên ảnh lệch nhẹ. Phần đầu đồ thị trong ảnh còn thấy tải 100 user của bài scaling.

| Chỉ số | Giá trị |
|---|---|
| Traffic | 18.75 req/s |
| avg / p50 / p95 / p99 | 238 / 176 / 295 / 1844 ms |
| Error ratio | 0.97% |
| Req/s theo instance | 9.40 và 9.35 |
| Tokens/s input / output | 1443 / 760 |

1. **Khoảng cách p95 và avg:** p95 (295 ms) chỉ cao hơn avg (238 ms) khoảng 57 ms, nhưng p99 là 1844 ms. Vậy đa số request có latency gần nhau, còn một nhóm nhỏ (dưới 5%) rất chậm. avg và p95 đều không cho thấy nhóm này.
2. **Nginx có chia đều không:** có, 9.40 và 9.35 req/s.
3. **Vì sao input tokens/s lớn hơn output:** prompt gửi LLM gồm system prompt, tài liệu lấy từ retrieval và câu hỏi, còn câu trả lời chỉ là đoạn tài liệu. Lưu ý panel Tokens/s vẽ chồng (stacked), nên đường output nằm trên đường input.
4. **`curl http://localhost:8080/metrics`:** trả **404**. `nginx.conf` chặn đường này, vì metrics lộ thông tin nội bộ (route, lưu lượng, model, chi phí). Prometheus scrape trực tiếp từng agent trong mạng nội bộ.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...

---

## Phụ lục: Exercise 7.1 (đọc metrics)

Output rút gọn từ `/metrics` của agent v2, sau một request `/ask` và hai URL lạ (`/wp-admin`, `/.env`):

```text
http_requests_total{method="POST",route="/ask",status="200"} 1.0
http_requests_total{method="GET",route="unmatched",status="404"} 2.0
agent_in_flight_requests 0.0
http_request_duration_seconds_bucket{le="0.3",method="POST",route="/ask"} 1.0
llm_tokens_total{model="mock-llm-small",type="input"} 91.0
llm_tokens_total{model="mock-llm-small",type="output"} 55.0
agent_question_length_chars_bucket{le="50.0"} 1.0
agent_question_length_chars_count 1.0
agent_question_length_chars_sum 40.0
```

1. **Counter:** `http_requests_total` (chỉ tăng). **Gauge:** `agent_in_flight_requests` (tăng và giảm). **Histogram:** `http_request_duration_seconds` (chia theo bucket).
2. **Vì sao dùng `route.path`:** hai URL lạ được gộp vào một series `route="unmatched"`. Nếu dùng URL thật, mỗi URL bot quét sẽ tạo thêm series mới. Hàng nghìn URL lạ làm số series tăng không giới hạn (cardinality cao), khiến Prometheus tốn RAM và truy vấn chậm.

**Metric thêm mới:** `agent_question_length_chars`, kiểu Histogram, các bucket 20, 50, 100, 200, 500, 1000, 2000 (trong `develop/app.py`). Không đưa độ dài vào label vì có quá nhiều giá trị khác nhau.
