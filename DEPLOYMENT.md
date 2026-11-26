# Deployment Information

## Public URL

https://agent-production-3bb32641.up.railway.app

## Platform

Railway: build từ `06-lab-complete/Dockerfile`, cấu hình ở `06-lab-complete/railway.toml`, kèm một service Redis.

## Test Commands

Đặt `BASE` là URL public và `AGENT_API_KEY` là key đã đặt trên nền tảng. Mỗi lệnh chỉ in mã HTTP.

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # mong đợi 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # mong đợi 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # mong đợi 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # mong đợi 200
```

### Kết quả (2026-11-26 22:31:05 +07:00)

```text
health          : 200
ready           : 200
ask, không key  : 401
ask, có key     : 200
```

`python check_production_ready.py --static-only --public-url <URL>`:

```text
✅ Public URL: GET https://agent-production-3bb32641.up.railway.app/health → 200
```

Log trên Railway (`railway logs --service agent`), hiển thị theo định dạng của Railway:

```text
[INFO]  ts="2026-11-26T15:30:45.334423+00:00" event="startup" environment="production" port=8080
[INFO]  ts="2026-11-26T15:31:06.935675+00:00" event="request" method="GET" path="/ready" status=200 ms=136.6
[INFO]  ts="2026-11-26T15:31:07.615909+00:00" event="request" method="POST" path="/ask" status=401 ms=5.5
```

## Cách deploy

Chạy trong `06-lab-complete/`:

```bash
railway login
railway init --name day14-agent
railway add --database redis
railway add --service agent
# AGENT_API_KEY: sinh ngẫu nhiên, truyền qua stdin
python -c 'import secrets,sys;sys.stdout.write(secrets.token_urlsafe(32))' | railway variable set AGENT_API_KEY --stdin --service agent --skip-deploys
railway variable set 'REDIS_URL=${{Redis.REDIS_URL}}' ENVIRONMENT=production RATE_LIMIT_PER_MINUTE=10 DAILY_BUDGET_USD=1.0 --service agent --skip-deploys
railway up --service agent --ci
railway domain --service agent
```

Khi deploy, CLI cảnh báo `railway.toml` (Config as Code) đã deprecated và file hiện có chỉ còn hoạt động tới 2026-12-01.

## Environment Variables Set

Giá trị secret chỉ đặt trên nền tảng, không ghi trong repo.

| Biến | Giá trị |
|---|---|
| `AGENT_API_KEY` | (secret) |
| `REDIS_URL` | tham chiếu tới service Redis: `${{Redis.REDIS_URL}}` |
| `ENVIRONMENT` | `production` |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1.0` |
| `PORT` | do Railway cấp |

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
