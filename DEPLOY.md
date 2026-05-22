# 部署進度與後續步驟

本機已完成的準備工作見下方「已完成」。Supabase 與 Vercel 上線仍需你提供帳號與憑證。

## 已完成

- 以 `uv` 安裝專案依賴（`task install`）
- 本機 SQLite 資料庫已初始化（`instance/easy_social.sqlite`）
- 單元測試通過（`task test-unit`，14 passed）
- 已安裝 Vercel CLI（`vercel --version`）
- 已新增 `.env.example` 範本

> **說明：** 本機 Poetry 在 Python 3.14 上無法執行，`Taskfile.yml` 已改為優先使用 `uv run`；若你的 Poetry 正常，仍會自動走 `poetry install`。

## 你需要完成的步驟

### 1. 建立 Supabase 專案

1. 登入 https://supabase.com → **New project**
2. 記下資料庫密碼與 **project ref**

### 2. 填寫本機 `.env`

```bash
cd easy-social
cp .env.example .env
# 編輯 .env，填入 Supabase 的 Transaction pooler 連線與 API 金鑰
```

連線字串位置：**Project Settings → Database → Transaction pooler**（port `6543`，username 為 `postgres.<project-ref>`）。

### 3. 初始化 Supabase（有 `.env` 後執行）

```bash
task setup-supabase
task test-supabase-connection
```

可選假資料：

```bash
task import-fake-data
```

### 4. 登入並部署 Vercel

```bash
vercel login
cd easy-social
vercel          # 第一次互動設定
```

在 Vercel 專案 **Settings → Environment Variables** 加入與 `.env` 相同的六個變數（見 README），然後：

```bash
vercel deploy --prod
```

或於 Vercel 網站連結 Git 儲存庫並設定 Root Directory 為 `easy-social`。

## 環境變數對照

| 變數 | 說明 |
|------|------|
| `SECRET_KEY` | 長隨機字串 |
| `DATABASE_URL` | Transaction pooler URI（6543） |
| `MEDIA_STORAGE_BACKEND` | `supabase` |
| `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | service_role（僅伺服器端） |
| `SUPABASE_STORAGE_BUCKET` | `easy-social-media` |

## 提供憑證後可代跑

把 `.env` 建好（或把 Supabase / Vercel 變數貼給我）後，在 Agent 模式可繼續執行：

- `task setup-supabase`
- `task test-supabase-connection`
- `vercel deploy`（需你先 `vercel login`）
