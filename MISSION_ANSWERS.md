# Day 14 Lab — Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

Các số dòng dưới đây thuộc `01-localhost-vs-production/develop/app.py`.

| # | Dòng | Anti-pattern | Hậu quả khi lên production |
|---|---|---|---|
| 1 | 17–18 | Hardcode API key và chuỗi kết nối database (kèm mật khẩu) | Ai đọc được repo là có secret. Xoá ở commit sau vẫn còn trong lịch sử git, nên phải đổi key. |
| 2 | 34 | In API key ra log (dòng 33, 38 còn in cả câu hỏi và câu trả lời) | Người có quyền xem log cũng lấy được key. Nội dung người dùng gửi có thể bị lưu lại. |
| 3 | 21–22 | Cấu hình viết cứng trong code | Muốn đổi giữa các môi trường phải sửa code và deploy lại. |
| 4 | 33–38, 48 | Dùng `print()` thay cho logging | Không có log level hay timestamp, khó lọc và tìm kiếm. |
| 5 | toàn file | Không có endpoint `/health` | Nền tảng không có cách hỏi app còn hoạt động đúng không, nhất là khi tiến trình còn sống nhưng bị treo. |
| 6 | 51 | `host="localhost"` | Chỉ nhận kết nối từ chính máy đó. Chạy trong container thì bên ngoài không gọi vào được. |
| 7 | 52 | Cố định cổng 8000, không đọc biến `PORT` | Railway/Render cấp cổng qua `PORT`; app nghe sai cổng thì request không tới được. |
| 8 | 53 | `reload=True` | Chế độ dành cho lúc code: tốn thêm một tiến trình theo dõi file, và app tự khởi động lại khi file đổi. |

### Exercise 1.2: Chạy bản develop

Chạy `python app.py` trong `develop/` (Python 3.12.10 trên Windows), rồi gọi:

```text
$ curl -i -X POST "http://localhost:8000/ask?question=Hello"
HTTP/1.1 200 OK
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}

$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 422 Unprocessable Entity
{"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}

$ curl -i http://localhost:8000/health
HTTP/1.1 404 Not Found
{"detail":"Not Found"}
```

Log server (đã che key):

```text
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-****(đã che)
[DEBUG] Response: Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé.
INFO:     127.0.0.1:52797 - "POST /ask?question=Hello HTTP/1.1" 200 OK
```

`netstat` cho thấy server chỉ nghe ở `127.0.0.1:8000`.

**Nhận xét:** app trả lời được, nhưng chưa sẵn sàng cho production: key bị in ra log, không có health check, và chỉ nhận kết nối nội bộ. Bản này nhận `question` qua query nên gửi JSON bị 422.

### Exercise 1.3: So sánh develop và production

Đã chạy bản production sau khi `cp .env.example .env`:

| Request | Kết quả |
|---|---|
| `POST /ask` với `{"question":"Hello"}` | 200, trả `question`, `answer`, `model` |
| `POST /ask` với `{}` | 422, `{"detail":"question field is required"}` |
| `GET /health` | 200, `{"status":"ok", "uptime_seconds":1.3, "version":"1.0.0", ...}` |
| `GET /ready` | 200, `{"ready":true}` |

`netstat` cho thấy server nghe ở `0.0.0.0:8000`.

| Feature | Develop | Production | Tại sao quan trọng? |
|---|---|---|---|
| Config và secret | Viết cứng trong `app.py` | Đọc từ biến môi trường, gom ở `config.py`; thiếu `AGENT_API_KEY` khi `ENVIRONMENT=production` thì dừng ngay | Cùng một bộ code chạy được ở nhiều môi trường, secret không nằm trong code, cấu hình thiếu bị phát hiện lúc khởi động |
| Host và port | `localhost:8000` cố định | `HOST` (mặc định `0.0.0.0`), `PORT` | Gọi được vào container và dùng đúng cổng nền tảng cấp |
| Health check | Không có (404) | `GET /health` | Nền tảng phát hiện app hỏng để khởi động lại |
| Readiness | Không có | `GET /ready`, trả 503 khi chưa sẵn sàng | Load balancer chỉ gửi request tới instance đã sẵn sàng |
| Logging | `print()`, có in cả key | Dùng `logging` theo mẫu JSON; chỉ ghi độ dài câu hỏi và câu trả lời, kèm IP client | Log lọc và tìm được, không lộ key và nội dung người dùng (xem lỗi bên dưới) |
| Shutdown | Không có bước dọn dẹp riêng | `lifespan` đặt `is_ready=False` và ghi log khi tắt; có handler SIGTERM ghi log | Khi deploy hoặc scale xuống, request đang chạy cần được xử lý xong trước khi tiến trình thoát |
| Kiểm tra input | FastAPI bắt buộc query `question` | Thiếu hoặc rỗng `question` trong JSON thì trả 422 | Client nhận mã lỗi rõ ràng. Body không phải JSON chưa được xử lý riêng trong code |
| Debug reload | Luôn bật | Chỉ bật khi `DEBUG=true` (mặc định tắt) | Tránh dùng chế độ phát triển trên production |
| CORS | Không cấu hình | Lấy danh sách origin từ `ALLOWED_ORIGINS`, mặc định `*` | Giới hạn website nào được gọi API từ trình duyệt; production nên bỏ `*`. CORS không thay cho xác thực |

**Ví dụ lỗi đã sửa:** `develop/app.py:34` in API key ra log. `production/app.py:111-115` chỉ ghi tên sự kiện, độ dài câu hỏi và IP client.

### Những điểm bản production vẫn chưa đúng

1. **`.env` không được nạp.** Tôi đặt `APP_VERSION=9.9.9` trong `.env`, nhưng `/health` vẫn trả `"version":"1.0.0"`. `app.py` và `config.py` không gọi `load_dotenv()`.
2. **Mất log INFO khi không có `OPENAI_API_KEY`.** Lần chạy đầu không có dòng log JSON nào. `config.py:45` gọi `logging.warning()` lúc import, trước `basicConfig` ở `app.py:28`. Lời gọi này tự cấu hình root logger ở mức WARNING, nên `basicConfig` sau đó không có tác dụng. Khi chạy lại với một key giả, log JSON xuất hiện.
3. **Log sự kiện không phải JSON hợp lệ.** Dòng dưới đây bị `json.loads` báo lỗi `Expecting ',' delimiter`, vì chuỗi `json.dumps` nằm trong `"msg"` mà dấu ngoặc kép không được escape:

```text
{"time":"2026-11-26 16:24:19,636","level":"INFO","msg":"{"event": "startup", "app": "AI Agent", "version": "1.0.0", "env": "development", "port": 8000}"}
```

**Giới hạn của lần kiểm tra:** chưa kiểm tra graceful shutdown. Server được tắt cưỡng bức bằng `taskkill /F` trên Windows, không gửi SIGTERM. Theo code, `handle_sigterm` chỉ ghi log, còn việc chờ request dựa vào uvicorn.

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

Dựa trên `02-docker/develop/Dockerfile`.

1. **Base image:** `python:3.11` (dòng 8), bản Python đầy đủ chạy trên Linux, không phải bản `slim`.
2. **Working directory:** `/app` (dòng 11). Các lệnh `COPY`, `RUN`, `CMD` phía sau chạy tương đối với thư mục này.
3. **Vì sao `COPY requirements.txt` trước code:** mỗi bước tạo một layer có cache. Docker dùng lại cache khi lệnh và file đầu vào không đổi; một layer phải build lại thì các layer sau nó cũng build lại. Vì `requirements.txt` ít thay đổi hơn code, khi chỉ sửa `app.py` thì bước `pip install` (dòng 17) vẫn lấy từ cache. `--no-cache-dir` chỉ tắt cache tải gói của pip, không tắt layer cache của Docker.
4. **`CMD` và `ENTRYPOINT`:** `CMD` là lệnh hoặc tham số mặc định, bị thay thế khi thêm lệnh sau tên image trong `docker run`. `ENTRYPOINT` là chương trình luôn được chạy; phần thêm sau tên image trở thành tham số của nó, muốn đổi phải dùng `--entrypoint`. Khi dùng cả hai ở dạng exec, `CMD` là tham số mặc định cho `ENTRYPOINT`. File này chỉ dùng `CMD ["python", "app.py"]`.

### Exercise 2.2: Build và chạy bản develop

Môi trường: Docker Engine 29.9.3 (linux/amd64). Chạy từ gốc repo.

```text
$ docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
$ docker run -d --name k5-day14-develop -p 8000:8000 my-agent:develop

$ curl -i -X POST "http://localhost:8000/ask?question=What%20is%20Docker"
HTTP/1.1 200 OK
{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}

$ curl -i http://localhost:8000/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":3.3,"container":true}
```

Debug bằng `docker logs` và `docker exec`: log cho thấy uvicorn nghe ở `0.0.0.0:8000`. Trong container, thư mục làm việc là `/app`, Python 3.11.18, và tiến trình `exec` chạy bằng `uid=0(root)`. Dockerfile này không có lệnh `USER`.

### Exercise 2.3: Multi-stage build

- **Stage 1 (`builder`, từ `python:3.11-slim`):** cài `gcc`, `libpq-dev`, rồi `pip install --user` các thư viện vào `/root/.local`.
- **Stage 2 (`runtime`, từ `python:3.11-slim`):** tạo user `appuser`, chỉ copy thư viện từ builder cùng `main.py` và `utils/mock_llm.py`, chuyển sang user thường, khai báo `HEALTHCHECK`, rồi chạy uvicorn với 2 worker.

```text
$ docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
$ docker images my-agent
IMAGE               ID             DISK USAGE   CONTENT SIZE
my-agent:advanced   ad254273139f        240MB         57.4MB
my-agent:develop    c4bcc6d69251       1.67GB          426MB
```

#### Image size comparison

| Chỉ số | Develop | Production | Giảm |
|---|---:|---:|---:|
| Disk usage | 1.67 GB (khoảng 1670 MB) | 240 MB | khoảng 85,6% |
| Content size | 426 MB | 57.4 MB | khoảng 86,5% |

`docker image inspect ... {{.Size}}` trả 1667779861 byte (develop) và 239815323 byte (advanced).

**Vì sao nhỏ hơn:**
- Phần chênh lệch chủ yếu đến từ **base image**: bản develop dùng `python:3.11` đầy đủ, còn runtime của production dùng `python:3.11-slim`.
- **Multi-stage** giữ `gcc`, `libpq-dev` và các file trung gian ở stage builder. Image cuối chỉ nhận thư viện đã cài (layer `COPY /root/.local`, 40.8 MB). Nếu dùng một stage `slim` và cài `gcc` thì chúng sẽ nằm trong image.
- Phép so sánh này thay đổi cả base image lẫn cách build, nên không tách được riêng phần giảm do multi-stage.

Chạy thử image production: `POST /ask` với JSON trả 200. `docker exec` cho thấy `uid=999(appuser)` và không có `gcc`.

### Exercise 2.4: Docker Compose stack

#### Sơ đồ

```text
Client (máy host)
   |  HTTP :80   (cổng 443 được map nhưng nginx.conf không listen 443)
   v
+------------------- network "internal" (bridge) -------------------+
|  nginx  --- HTTP agent:8000 --->  agent (FastAPI, 2 uvicorn worker) |
|                                     . . . > redis:6379  (volume redis_data)
|                                     . . . > qdrant:6333 (volume qdrant_data)
+-------------------------------------------------------------------+
---> : request thực tế        . . . > : đã cấu hình URL, code hiện chưa dùng
```

| Service | Vai trò | Cổng ra host |
|---|---|---|
| `nginx` | Reverse proxy, giới hạn tốc độ, thêm security header | 80, 443 |
| `agent` | API FastAPI | Không |
| `redis` | Dành cho session và rate limit | Không |
| `qdrant` | Vector database dành cho RAG | Không |

Các service gọi nhau bằng **tên service** (DNS nội bộ của Docker). Theo `depends_on`, `agent` đợi `redis` và `qdrant` healthy rồi mới khởi động; `nginx` khởi động sau `agent` nhưng không đợi `agent` healthy.

#### Chạy và test qua Nginx

Repo không có sẵn `.env.local`, nên tạo file rỗng trước.

```text
$ cd 02-docker/production && touch .env.local
$ docker compose -p k5-day14-docker up -d --build
$ docker compose -p k5-day14-docker ps        (sau khoảng 35 giây)
SERVICE   STATUS                    PORTS
agent     Up 35 seconds (healthy)   8000/tcp
nginx     Up 35 seconds             0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
qdrant    Up 46 seconds (healthy)   6333-6334/tcp
redis     Up 46 seconds (healthy)   6379/tcp

$ curl -i http://localhost/health
HTTP/1.1 200 OK
Server: nginx
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
{"status":"ok","uptime_seconds":34.1,"version":"2.0.0","timestamp":"2026-11-26T13:59:36.828566"}

$ curl -i -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question":"Explain microservices"}'
HTTP/1.1 200 OK
Server: nginx
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

- **Rate limit:** gửi 60 request song song tới `/` được 34 mã 200 và 26 mã 429. Log Nginx ghi `limiting requests ... by zone "api_limit"` (cấu hình `rate=10r/s`, `burst=20`).
- **Kết nối nội bộ:** từ container `agent`, mở được kết nối TCP tới `redis:6379` và `qdrant:6333`.
- Test xong đã dọn bằng `docker compose -p k5-day14-docker down -v`.

#### Điểm khác với chú thích trong file

- Comment ghi agent có 2 replica, nhưng compose không cấu hình replica nên chỉ có **1 container** `agent` (trong đó uvicorn chạy 2 worker). Lần test này chưa kiểm tra cân bằng tải giữa nhiều container.
- `main.py` không đọc `REDIS_URL` hay `QDRANT_URL`. `redis-cli dbsize` trả 0 sau khi gọi `/ask`. Test TCP chỉ chứng minh mạng thông, không chứng minh app dùng hai service này.

## Part 3: Cloud Deployment

### Exercise 3.1: Deploy lên Railway (nền tảng chính)

- URL: https://agent-production-3bb32641.up.railway.app
- Project Railway gồm service `agent` (build từ `06-lab-complete/Dockerfile`) và service `Redis`.
- 4 lệnh tự kiểm: `/health` 200, `/ready` 200, `/ask` không key 401, `/ask` có key 200.
- Chi tiết, lệnh test và ảnh: [DEPLOYMENT.md](DEPLOYMENT.md)

### Exercise 3.2: So sánh `railway.toml` và `render.yaml`

So sánh hai file trong `06-lab-complete/`. `render.yaml` chưa được deploy thử.

| Điểm khác | `railway.toml` | `render.yaml` | Vì sao |
|---|---|---|---|
| Định dạng | TOML | YAML | Theo quy ước của từng nền tảng |
| Phạm vi | Cách build và chạy **một service** | Blueprint khai báo **nhiều service** (web và Key Value) | Render Blueprint mô tả cả hạ tầng; ở Railway, file này gắn với từng service |
| Redis | Không khai báo; thêm bằng CLI hoặc dashboard | Khai báo `type: keyvalue` ngay trong file | Hệ quả của phạm vi ở trên |
| Biến môi trường | Không ghi trong file; đặt bằng `railway variable set` | Liệt kê trong `envVars` | Blueprint cần biết service cần biến nào để tạo |
| Secret | Đặt trên Railway | `generateValue: true`, Render tự sinh | Cả hai đều không ghi giá trị secret vào repo |
| Nối Redis | Biến tham chiếu `${{Redis.REDIS_URL}}` | `fromService` với `property: connectionString` | Không phải chép chuỗi kết nối bằng tay |
| Build | `builder = "DOCKERFILE"` | `runtime: docker` | Cùng dùng `06-lab-complete/Dockerfile` |
| Thư mục | Chạy `railway up` từ `06-lab-complete/` | `rootDir: 06-lab-complete` | Render lấy code từ cả repo Git, còn `railway up` tải thư mục từ máy lên |
| Health check | `healthcheckPath`, `healthcheckTimeout` | `healthCheckPath` | Cùng trỏ tới `/health`, khác tên khoá |
| Restart | `restartPolicyType = "ON_FAILURE"`, tối đa 3 lần | Không cấu hình trong file | File Railway cho khai báo chính sách này |
| Gói và nguồn deploy | Không khai báo | `plan: free`; deploy từ GitHub | Render cần biết gói cho từng service |

Cả hai đều không đặt lệnh start, nên dùng `CMD` trong Dockerfile. `CMD` này đọc biến `PORT` do nền tảng cấp.

File mẫu trong `03-cloud-deployment/` khác ở chỗ build không dùng Dockerfile (`NIXPACKS` và `runtime: python`) và ghi `startCommand` trực tiếp.

### Exercise 3.3: Pipeline CI/CD của Cloud Run

Theo chú thích trong `cloudbuild.yaml`, pipeline được kích hoạt khi push lên `main`; trigger này phải cấu hình riêng, file không khai báo. Pipeline có 4 bước nối tiếp bằng `waitFor`:
1. **test:** cài dependencies và chạy `pytest tests/`; test lỗi thì các bước sau không chạy.
2. **build:** build Docker image, gắn tag `$COMMIT_SHA` và `latest`, dùng `--cache-from` để tận dụng cache.
3. **push:** đẩy các tag lên `gcr.io`.
4. **deploy:** `gcloud run deploy` image theo `$COMMIT_SHA` ở `asia-southeast1`, 1–10 instance, lấy `OPENAI_API_KEY` từ Secret Manager.

`service.yaml` mô tả service theo kiểu Infrastructure as Code (scale 1–10, concurrency 80, giới hạn 1 CPU và 512Mi, secret lấy từ Secret Manager, `startupProbe` gọi `/ready`, `livenessProbe` gọi `/health`). Pipeline không dùng file này mà deploy bằng tham số dòng lệnh, và lệnh đó không truyền `AGENT_API_KEY`.

## Part 4: API Security

### Exercise 4.1: API key authentication

Dựa trên `04-api-gateway/develop/app.py`.

- **Key được kiểm tra ở đâu:** hàm `verify_api_key` (dòng 39–54) đọc header `X-API-Key`. Endpoint `/ask` gắn hàm này qua `Depends` (dòng 70). `/` và `/health` không cần key.
- **Sai key thì sao:** thiếu key trả **401**, sai key trả **403**.
- **Đổi (rotate) key:** đổi biến môi trường `AGENT_API_KEY` rồi khởi động lại app, vì key được đọc một lần lúc import (dòng 35). Muốn không gián đoạn client, app cần tạm chấp nhận cả key cũ và key mới, chuyển client sang key mới rồi bỏ key cũ. Code hiện chưa hỗ trợ việc này.
- **Điểm yếu:** có key mặc định nếu quên đặt biến (dòng 35), in key ra màn hình khi khởi động (dòng 91–92), so sánh bằng `!=` thay vì `hmac.compare_digest`.

Chạy bằng `AGENT_API_KEY=secret-key-123 python app.py` (key demo):

```text
$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

(thêm -H "X-API-Key: wrong-key")
HTTP/1.1 403 Forbidden
{"detail":"Invalid API key."}

(thêm -H "X-API-Key: <key đúng>")
HTTP/1.1 200 OK
{"question":"Hello","answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

### Exercise 4.2: JWT authentication

**Luồng:**
1. Client gửi username/password tới `POST /auth/token`.
2. Server kiểm tra, rồi ký JWT bằng HS256, gồm `sub`, `role`, `iat`, `exp` (hết hạn sau 60 phút).
3. Client gửi `Authorization: Bearer <token>`.
4. `verify_token` kiểm tra chữ ký và hạn dùng, rồi lấy user và role từ token, không cần tra database.

Payload chỉ được mã hoá base64, **không được mã hoá bí mật**, nên không đặt dữ liệu nhạy cảm vào đó. Khi giải mã token đã lấy, tôi đọc được `{"sub":"student","role":"user","iat":...,"exp":...}`.

| Request tới server production | Kết quả |
|---|---|
| Không có token | 401, `Authentication required...`, có header `www-authenticate: Bearer` |
| Token không hợp lệ | 403, `Invalid token.` |
| Login sai mật khẩu | 401, `Invalid credentials` |
| Token hợp lệ | 200 |

```text
$ curl -s -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" \
    -d '{"username":"student","password":"demo123"}'
(nhận access_token, đã che)

$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer <TOKEN đã che>" \
    -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
HTTP/1.1 200 OK
{"question":"Explain JWT","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

**Rủi ro:** `JWT_SECRET` có giá trị mặc định nằm trong code (`auth.py:22`). Nếu production không đặt biến này, người đọc được code có thể tự ký token với role `admin`.

### Exercise 4.3: Rate limiting

- **Thuật toán:** sliding window. Code lưu timestamp của từng request trong một `deque` và bỏ các mốc cũ hơn 60 giây. Docstring gọi là "Sliding Window Counter", nhưng cách lưu từng mốc thời gian thường được gọi là sliding window log. Không phải token bucket.
- **Giới hạn:** role `user` được 10 request/phút, role `admin` được 100 request/phút (`rate_limiter.py:86-87`).
- **Nới giới hạn cho admin:** `app.py:141` chọn limiter theo `role` trong token. Admin **không được bỏ qua** rate limit, chỉ có ngưỡng cao hơn. Muốn bỏ qua hẳn thì phải thêm nhánh không gọi `limiter.check` cho admin.

Dùng token của `student` gọi 20 lần liên tiếp. Trước đó request `Explain JWT` đã chiếm 1 lượt, nên **lần 1–9 trả 200, lần 10–20 trả 429**.

```text
--- request 9
HTTP/1.1 200 OK
{"question":"Test 9","answer":"...","usage":{"requests_remaining":0,"budget_remaining_usd":0.000196}}

--- request 10
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795704606
retry-after: 56
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":56}}
```

Tài khoản `teacher` (role admin) gọi 20 lần: cả 20 lần trả 200.

**Hạn chế:** dữ liệu nằm trong RAM nên mất khi khởi động lại. Chạy N instance hoặc N worker thì mỗi tiến trình đếm riêng, giới hạn thực tế có thể gần gấp N lần. `/auth/token` không có rate limit, nên không chặn được việc dò mật khẩu.

### Exercise 4.4: Cost guard

**Cách code hiện tại hoạt động (`cost_guard.py`):**
- Trước khi gọi LLM, `check_budget` kiểm tra tổng chi toàn hệ thống (ngưỡng 10 USD, trả 503), rồi chi tiêu trong ngày của từng user (ngưỡng 1 USD, trả 402). Dùng từ 80% thì ghi cảnh báo.
- Sau khi gọi, `record_usage` cộng số token và tính tiền: 0.00015 USD cho 1K token input, 0.0006 USD cho 1K token output. Trong `app.py`, số token chỉ được ước lượng bằng số từ nhân 2.

Qua API không dễ chạm mức 1 USD (10 request mới tốn 0.000196 USD). Vì vậy tôi gọi trực tiếp class với ngân sách nhỏ, không sửa file:

```text
CostGuard(daily_budget_usd=0.001)
u1 trước khi dùng          -> được phép
record_usage(2000, 2000)   -> cost 0.0015
u1 gọi tiếp                -> 402 {'error': 'Daily budget exceeded', 'used_usd': 0.0015, 'budget_usd': 0.001, 'resets_at': 'midnight UTC'}
u2                         -> được phép
```

**Cách tôi sẽ làm theo đề (10 USD mỗi user mỗi tháng, lưu trong Redis).** Đây là thiết kế, chưa chạy trong Part 4:
1. Key là `budget:{user_id}:{YYYY-MM}`, tính tháng theo UTC. Sang tháng mới sẽ dùng key mới, nên ngân sách tự reset. Đặt TTL khoảng 32 ngày để dọn key cũ.
2. Trước khi gọi LLM, ước lượng chi phí. Nếu `đã dùng + ước lượng > 10` thì trả 402.
3. Bước kiểm tra và cộng tiền phải **nguyên tử**, ví dụ bằng Lua script. Lời giải mẫu trong `CODE_LAB.md` gọi `GET` rồi mới `INCRBYFLOAT`, nên nhiều request đồng thời có thể cùng qua bước kiểm tra và vượt ngân sách.
4. Sau khi LLM trả lời, cộng hoặc trừ phần chênh giữa chi phí thật và ước lượng. Nếu gọi lỗi và không bị tính phí thì hoàn lại phần đã giữ.

**Vì sao cần cả hai:** rate limit chặn số request trong một khoảng thời gian, còn cost guard chặn tổng tiền. Một user gọi đúng giới hạn nhưng liên tục, hoặc gửi prompt rất dài, vẫn có thể tốn nhiều tiền.

### Lỗi tìm thấy trong code mẫu production

| Vị trí | Vấn đề | Bằng chứng |
|---|---|---|
| `app.py:160` | `budget_remaining_usd` thực ra trả **số tiền đã dùng** | Khi chạy, giá trị tăng từ 0.000019 lên 0.000196, trong khi `/me/usage` báo còn 0.999804 |
| `cost_guard.py:50-51, 104` | `_global_cost` không reset theo ngày (`_global_today` không được dùng lại) | Đọc code, chưa chạy kiểm tra |
| `cost_guard.py:76` | Chỉ so chi phí đã dùng, không cộng chi phí ước lượng, nên request cuối có thể làm vượt ngân sách | Đọc code |
| `cost_guard.py:49-51` | Chi tiêu lưu trong RAM: mất khi restart, không chia sẻ giữa các instance | Đọc code |

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks

Dựa trên `05-scaling-reliability/develop/app.py`. Bản này đã có sẵn hai endpoint; tôi chạy và phân tích, không viết lại.

| | `/health` (liveness, dòng 104–144) | `/ready` (readiness, dòng 147–168) |
|---|---|---|
| Câu hỏi | Tiến trình còn sống không? | Đã nên gửi request vào chưa? |
| Khi lỗi, nền tảng thường | Khởi động lại container | Tạm ngừng gửi traffic, không cần restart |
| Trong code | Trả status, uptime, kiểm tra bộ nhớ nếu có `psutil` | Trả 503 khi cờ `_is_ready` là `False` |

```text
GET /health -> 200 {"status":"ok","uptime_seconds":2.3,"version":"1.0.0",...,"checks":{"memory":{"status":"ok","used_percent":9.6}}}
GET /ready  -> 200 {"ready":true,"in_flight_requests":1}
```

`in_flight_requests` bằng 1 vì middleware đếm cả chính request `/ready`. Ở bản này `/health` trả HTTP 200 kể cả khi `status` là `degraded`, và `/ready` không kiểm tra dependency bên ngoài.

### Exercise 5.2: Graceful shutdown

**Cách test:** chạy `app.py` trong container `python:3.11-slim` (Linux). Mock LLM bình thường chỉ chậm khoảng 0.1 giây, nên tôi dùng một script tạm ngoài repo để kéo độ trễ lên 6 giây, không sửa code trong repo. Gửi một request, khoảng 2 giây sau chạy `docker stop -t 30` (gửi SIGTERM).

```text
Request đang chạy dở: {"answer":"..."}  HTTP 200 after 6.009054s

INFO:     "POST /ask?question=Long%20task HTTP/1.1" 200 OK
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO 🔄 Graceful shutdown initiated...
INFO ✅ Shutdown complete
INFO:     Finished server process [1]
INFO Received signal 15 — uvicorn will handle graceful shutdown
exit code 0
```

Gọi `/health` sau khi container dừng thì không kết nối được.

- **Kết quả:** request đang chạy vẫn trả 200, sau đó app mới tắt với exit code 0.
- **Ai làm việc này:** uvicorn bắt SIGTERM, chờ request rồi chạy phần shutdown của `lifespan`. `handle_sigterm` (dòng 175–183) chỉ ghi log, và trong lần chạy này dòng log đó xuất hiện sau cùng. `timeout_graceful_shutdown=30` (dòng 198) giới hạn thời gian chờ.
- **Lưu ý:** `/ask` là `async def` nhưng gọi `ask()` dùng `time.sleep`, nên chặn event loop. Trong lúc đó tiến trình không xử lý được request khác, kể cả health check.

### Exercise 5.3: Stateless design

**Vấn đề:** nếu history nằm trong biến Python, mỗi instance có một bản riêng. Request sau tới instance khác sẽ không thấy history, và restart là mất.

**Cách bản `production/app.py` làm:** lưu mỗi session ở key Redis `session:{id}` dạng JSON, TTL 3600 giây (`save_session`, dòng 59–65), giữ tối đa 20 message (dòng 86–87). Instance nào cũng đọc được cùng dữ liệu.

**Chỗ chưa thật sự stateless hoặc chưa đúng:**

| Vị trí | Vấn đề | Bằng chứng |
|---|---|---|
| Dòng 42–45 | Không nối được Redis lúc khởi động thì âm thầm chuyển sang dict trong RAM; khi đó `/ready` vẫn báo ready | Đọc code. Production nên báo not ready hoặc dừng |
| Dòng 76–90 | Đọc, sửa rồi ghi cả session, không nguyên tử: hai request đồng thời cùng session có thể ghi đè nhau. Nên dùng `RPUSH`/`LTRIM` | Đọc code, chưa tái hiện |
| Dòng 154 | `turn` bị lệch 1: đã thêm câu hỏi hiện tại vào history rồi còn cộng 1 | Cả 10 request tạo session mới đều trả `turn 2` |

### Exercise 5.4: Load balancing

```text
$ touch .env.local
$ docker compose -p k5-day14-scaling up -d --build --scale agent=3
agent-1, agent-2, agent-3   Up (healthy)   8000/tcp
nginx                       Up             0.0.0.0:8080->80/tcp
redis                       Up (healthy)   6379/tcp
```

Gửi 10 request `POST /chat` qua cổng 8080: cả 10 trả 200, `storage=redis`, luân phiên đều giữa 3 instance:

```text
200 instance-61d0e7 172.19.0.5:8000
200 instance-c58950 172.19.0.3:8000
200 instance-91394f 172.19.0.4:8000
200 instance-61d0e7 172.19.0.5:8000
...
```

`served_by` do app trả về, còn địa chỉ IP lấy từ header `X-Served-By` của Nginx. Nginx lấy danh sách IP từ DNS của tên `agent` và phân theo round-robin.

**Khi một instance chết (`docker kill`):** tôi thử hai lần và được kết quả khác nhau.

| Lần | Giới hạn chờ của curl | Kết quả 6 request sau khi kill |
|---|---:|---|
| 1 | 20 giây | 4 trả 200; 2 (thứ 3 và 6) không có phản hồi trong 20 giây |
| 2 (stack mới) | 90 giây | Cả 6 trả 200; request thứ 3 mất 3.18 giây, các request còn lại khoảng 0.12–0.15 giây |

Ở lần 2, log Nginx có `connect() failed (113: Host is unreachable) while connecting to upstream`. Như vậy traffic chuyển được sang instance khác, nhưng **không phải lúc nào cũng liền mạch**. Tôi chưa xác định chắc vì sao hai lần khác nhau. Giả thuyết là thời gian Nginx chờ kết nối tới IP đã chết: `nginx.conf` không đặt `proxy_connect_timeout` (mặc định 60 giây). Ngoài ra, dòng `resolver` không làm khối `upstream` tĩnh tự cập nhật IP, và Nginx mặc định không gửi lại request `POST` đã chuyển tới upstream.

### Exercise 5.5: Test stateless

`python test_stateless.py` gửi 5 câu trong cùng một session rồi đọc history. Script **không tự tắt instance nào**.

```text
Request 1: [instance-61d0e7]
Request 2: [instance-c58950]
Request 3: [instance-91394f]
Request 4: [instance-61d0e7]
Request 5: [instance-c58950]
Instances used: 3 instance
Total messages: 10        (5 user + 5 assistant, đủ và đúng thứ tự)
```

**Giải thích:** 5 request của một session đi qua 3 instance mà history vẫn đủ, vì state nằm trong Redis.

**Test thêm bằng tay (lần 1):** tạo session, kill `agent-1`, gửi tiếp trong cùng session. History còn nguyên, đọc được qua instance còn sống: có `before kill` và các câu 1, 2, 4, 5. Câu 3 và 6 (hai request không phản hồi) không có trong history. Sau đó `docker stop` một instance khác (SIGTERM): log có `Instance instance-91394f shutting down`, exit code 0.

**Khi Redis chết** (đo với đủ 3 agent):

| Request | Gọi bên trong một agent | Gọi qua Nginx |
|---|---|---|
| `/health` | 200 `"status":"degraded"`, 4.00 s | 200, 3.90 s |
| `/ready` | 503 `Redis not available`, 3.85 s | 503, 11.60 s |
| `POST /chat` | 500, 3.87 s | không đo |

- `/health` vẫn 200 vì tiến trình còn sống; restart agent không sửa được Redis. `/ready` trả 503 để báo đừng gửi traffic.
- Qua Nginx, `/ready` lâu hơn; nhiều khả năng do `proxy_next_upstream ... http_503` thử lần lượt 3 instance.
- Mỗi lần gọi mất khoảng 4 giây và `/chat` trả 500 thô. Nên đặt timeout cho Redis client và trả lỗi 503 rõ ràng.
- Một lần đo đầu, lúc chỉ còn 1 agent sống, `/ready` qua Nginx không phản hồi trong 30 giây. Lần đó bị nhiễu bởi 2 instance đã tắt nên tôi không dùng để kết luận.
- Compose không gắn volume cho Redis. Sau khi `stop` rồi `start` cùng container, history vẫn đọc được, nhưng chưa có gì bảo đảm dữ liệu còn khi container bị xoá và tạo lại.

Test xong đã dọn bằng `docker compose -p k5-day14-scaling down`.

## Part 6: Final Project

Code nằm trong `06-lab-complete/`. Không sửa `check_production_ready.py`.

### Output script chấm

> **Chưa có một lần chạy `PASS 12/12`.** Dưới đây là hai lần chạy ở hai môi trường. Cần chạy lại bản đầy đủ trong WSL2 và thay phần này bằng output đó.

**Lần 1: bản đầy đủ, Python trên Windows** (`os.name = nt`)

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ⚠️  Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 11/12 tiêu chí đạt · 42/42 checks passed
  ⚠️  Chưa kiểm tra được: Graceful shutdown
```

Image 273 MB; `docker stop` exit code 0 trong 0.8 s. Lý do ⚠️: Windows không gửi được SIGTERM cho process uvicorn.

**Lần 2: trong container Linux `python:3.11-slim`** (`os.name = posix`, `--skip-docker`)

```text
     ✅ Khi chạy: SIGTERM lúc đang có request → request vẫn 200, process tự thoát — exit code 0
  Result: 10/12 tiêu chí đạt · 39/39 checks passed
  ⚠️  Chưa kiểm tra được: Dockerfile (multi-stage, < 500 MB), Graceful shutdown
```

Hai tiêu chí ⚠️ ở lần này là do `--skip-docker` bỏ qua các check Docker.

### Kiểm tra thêm bằng `docker compose` (giới hạn 10 request/phút, API key ngẫu nhiên)

| Trường hợp | Kết quả |
|---|---|
| 30 request đồng thời, 2 worker | Đúng 10 mã 200, 20 mã 429 |
| Header khi 429 | `retry-after: 60` |
| Thiếu `question`, chuỗi toàn khoảng trắng, body không phải JSON, dài 2001 ký tự | Đều 422, không có stack trace |
| Sai API key | 401 |
| Tắt Redis | `/health` 200, `/ready` 503 (khoảng 4 s), `/ask` 503 |
| Bật lại Redis | `/ready` 200 mà không phải restart agent |
| `docker compose stop agent` | Exit code 0, khoảng 1.2 s, có log `shutdown` |
| Log | Mọi dòng là JSON hoặc log của uvicorn; không tìm thấy API key trong log |
| User trong container | `uid=999(appuser)` |

### Các quyết định thiết kế

- **Rate limit:** sliding window bằng sorted set trong Redis. Xoá mốc cũ, đếm và thêm nằm trong một Lua script nên nguyên tử giữa nhiều worker. Redis chỉ lưu hash SHA-256 của API key.
- **Cost guard:** ngân sách **theo ngày (UTC)**, tính chung cho toàn service. Giữ trước chi phí ước lượng (input cộng 100 token output giả định) bằng Lua script, sau khi gọi LLM thì bù phần chênh, gọi lỗi thì hoàn lại. Thiết kế này dựa trên ý ở Exercise 4.4, khác ở chỗ tính theo ngày, không theo từng user mỗi tháng.
  - Giới hạn: nếu câu trả lời dài hơn 100 token thì phần vượt chỉ được cộng sau, nên tổng có thể vượt nhẹ ngân sách. Nếu tiến trình chết giữa chừng thì phần đã giữ không được hoàn lại.
- **Redis chết:** `/ask` trả 503 thay vì bỏ qua rate limit và budget (fail closed).
- **API key:** thiếu và sai đều trả 401, so sánh bằng `hmac.compare_digest`. Thiếu `AGENT_API_KEY` khi `ENVIRONMENT=production` thì app không khởi động.
- **Graceful shutdown:** không tự đăng ký signal handler; uvicorn xử lý SIGTERM, `lifespan` đóng kết nối Redis. `CMD` dùng `exec` để uvicorn là PID 1.
- **`/ask` là `def`:** chạy trong thread pool, nên `time.sleep` của mock LLM không chặn event loop (khác lưu ý ở Exercise 5.2).

## AI log

| Phần | Đã hỏi | AI đã làm | Tôi tự sửa và tự kiểm tra |
|---|---|---|---|
| Part 1 | Nhờ giải thích CP1, sau đó nhờ làm CP1 (Claude Code) | Đọc code, chạy hai bản app, gọi các endpoint, thử `.env` và log JSON, soạn toàn bộ phần Part 1. Không sửa code mẫu | _(tự điền sau khi kiểm tra lại)_ |
| Part 2 | Nhờ làm CP2 (Claude Code) | Đọc Dockerfile và compose, build hai image, đo kích thước, chạy container và stack, test qua Nginx, soạn toàn bộ phần Part 2. Không sửa code mẫu | _(tự điền sau khi kiểm tra lại)_ |
| Part 4 | Nhờ làm CP3 (Claude Code) | Đọc code, chạy hai bản app, test 401/403/200/429, gọi trực tiếp class cost guard, đề xuất thiết kế Redis, soạn toàn bộ phần Part 4. Không sửa code mẫu | _(tự điền sau khi kiểm tra lại)_ |
| Part 5 | Nhờ làm CP4 (Claude Code) | Đọc code, test SIGTERM trong container (dùng script tạm làm chậm mock LLM), chạy stack 3 instance, test cân bằng tải, kill instance, tắt Redis, soạn toàn bộ phần Part 5. Không sửa code mẫu | _(tự điền sau khi kiểm tra lại)_ |
| Part 6 | Nhờ làm CP5 (Claude Code) | **Viết toàn bộ code và cấu hình** trong `06-lab-complete/` (`app/*.py`, `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.env.example`, `railway.toml`, `render.yaml`), chạy script chấm và test thêm, soạn phần Part 6. Không sửa script chấm | _(tự điền sau khi kiểm tra lại)_ |
| Part 3 | Nhờ làm CP6 (Claude Code) | Cài Railway CLI, soạn phần so sánh config và mô tả pipeline Cloud Run; sau khi tôi tự đăng nhập Railway thì tạo project, đặt biến môi trường, deploy, chạy 4 lệnh tự kiểm và viết `DEPLOYMENT.md` |
| Part 7 Bước 1 | Nhờ làm CP7 (Claude Code) | Thêm metric `agent_question_length_chars`, chạy load test và eval, thêm 2 tài liệu vào knowledge base, viết `.github/workflows/eval.yml`, điền mục 1–3 và phụ lục của `BENCHMARK_REPORT.md` (gồm cả việc chọn ngưỡng SLO và viết nhận xét) | _(tự điền sau khi kiểm tra lại)_ |
| Part 7 Bước 2 | Nhờ làm CP8 (Claude Code) | Sửa `production/Dockerfile`, chép knowledge base sang stack production, chạy stack và Locust, **chụp 4 ảnh Part 7 bằng script tự động**, tìm trace và log, chạy thí nghiệm alert A, B, D, E, điền mục 4–6 của `BENCHMARK_REPORT.md` (gồm phân tích và kết luận) | _(tự điền sau khi kiểm tra lại)_ |
