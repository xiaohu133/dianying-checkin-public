import os
import sys
import json
import time
import logging
import threading
import uuid
from pathlib import Path
from datetime import datetime
import urllib.request
import urllib.error
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn

from dian_client import Dian115Client

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("dianying-checkin")

DATA_DIR = Path("/app/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_FILE = DATA_DIR / "config.json"
HISTORY_FILE = DATA_DIR / "history.json"

DEFAULT_GLOBAL_CONFIG = {
    "accounts": [],
    "checkin_time": os.getenv("DIAN115_CHECKIN_TIME", "00:05"), # HH:MM
    "tg_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
    "tg_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
    "tg_base_url": os.getenv("TELEGRAM_BASE_URL", "https://api.telegram.org"),
    "run_on_start": os.getenv("RUN_ON_START", "true").lower() in ("true", "1", "yes")
}

def load_config() -> dict:
    cfg = DEFAULT_GLOBAL_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                cfg.update(saved)
        except Exception as e:
            logger.warning("Failed to read config.json: %s", e)

    # Backward compatibility: migrate legacy single account if present
    migrated = False
    if "accounts" not in cfg or not isinstance(cfg.get("accounts"), list) or len(cfg["accounts"]) == 0:
        legacy_email = cfg.pop("email", "").strip()
        legacy_password = cfg.pop("password", "").strip()
        legacy_cookie = cfg.pop("cookie", "").strip()
        legacy_mode = cfg.pop("checkin_mode", "lucky")
        if legacy_email or legacy_cookie:
            cfg["accounts"] = [{
                "id": "acc_1",
                "name": legacy_email.split("@")[0] if legacy_email else "默认账号",
                "email": legacy_email,
                "password": legacy_password,
                "cookie": legacy_cookie,
                "checkin_mode": legacy_mode,
                "enabled": True
            }]
            migrated = True
        else:
            cfg["accounts"] = []

    if migrated:
        save_config(cfg)

    return cfg

def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Failed to save config: %s", e)

def load_history() -> list:
    if HISTORY_FILE.exists():
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def append_history(record: dict):
    history = load_history()
    history.insert(0, record)
    history = history[:100] # Keep latest 100
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Failed to append history: %s", e)

# Isolated Dian115 Client pool
client_pool_lock = threading.Lock()
_account_clients: dict[str, Dian115Client] = {}

def get_client_for_account(acc: dict) -> Dian115Client:
    acc_id = acc.get("id") or "acc_default"
    with client_pool_lock:
        if acc_id not in _account_clients:
            _account_clients[acc_id] = Dian115Client(
                cookie=acc.get("cookie", ""),
                email=acc.get("email", ""),
                password=acc.get("password", "")
            )
        else:
            cli = _account_clients[acc_id]
            cli.set_credentials(acc.get("email", ""), acc.get("password", ""))
            if acc.get("cookie"):
                cli.set_cookie(acc.get("cookie", ""))
        return _account_clients[acc_id]

def send_tg_notification(title: str, text_content: str):
    cfg = load_config()
    token = cfg.get("tg_bot_token", "").strip()
    chat_id = cfg.get("tg_chat_id", "").strip()
    base_url = cfg.get("tg_base_url", "https://api.telegram.org").strip().rstrip("/")
    if not token or not chat_id:
        return

    html = f"{title}\n\n{text_content}"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": html,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{base_url}/bot{token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            pass
    except Exception as e:
        logger.warning("Failed to send Telegram message: %s", e)

def execute_account_checkin(acc: dict, is_manual: bool = False) -> dict:
    acc_id = acc.get("id")
    acc_name = acc.get("name") or acc.get("email") or f"账号({acc_id})"
    mode = acc.get("checkin_mode", "lucky")
    mode_name = "🎲 运气签到" if mode == "lucky" else "📅 普通签到"

    logger.info("=== 正在执行账号签到: %s (%s, 手动=%s) ===", acc_name, mode_name, is_manual)

    cli = get_client_for_account(acc)

    # 1. 检验账号身份
    user_info = cli.get_account_info()
    if not user_info.get("authenticated"):
        msg = user_info.get("message") or "认证失效或未登录"
        logger.error("账号 %s 验证失败: %s", acc_name, msg)
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "account_id": acc_id,
            "account_name": acc_name,
            "success": False,
            "mode": mode_name,
            "message": msg,
            "username": "验证失败",
            "points": None,
            "award": 0
        }
        append_history(record)
        return record

    username = user_info.get("username") or acc_name

    # 2. 同步 Cookie 变动到配置
    if cli._cookie_str and cli._cookie_str != acc.get("cookie"):
        cfg = load_config()
        for a in cfg.get("accounts", []):
            if a.get("id") == acc_id:
                a["cookie"] = cli._cookie_str
                break
        save_config(cfg)

    # 3. 发起签到
    try:
        res = cli.signin(mode=mode)
        logger.info("账号 %s 签到结果: %s", acc_name, res)
    except Exception as e:
        err_msg = f"签到请求异常: {e}"
        logger.error(err_msg)
        record = {
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "account_id": acc_id,
            "account_name": acc_name,
            "success": False,
            "mode": mode_name,
            "message": err_msg,
            "username": username,
            "points": user_info.get("points"),
            "award": 0
        }
        append_history(record)
        return record

    success = bool(res.get("success", False))
    already = bool(res.get("already_checked_in", False))
    msg = res.get("message") or ("今日已签到" if already else "签到成功")
    award = res.get("award")

    # 4. 获取最新积分
    new_user_info = cli.get_account_info()
    current_points = new_user_info.get("points") if new_user_info.get("success") else user_info.get("points")
    streak = new_user_info.get("consecutive_signin") if new_user_info.get("success") else res.get("streak", 0)

    record = {
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "account_id": acc_id,
        "account_name": acc_name,
        "success": success,
        "mode": mode_name,
        "message": msg,
        "username": username,
        "points": current_points,
        "award": award if award is not None else 0,
        "streak": streak
    }
    append_history(record)
    return record

def execute_all_checkin(is_manual: bool = False) -> list:
    cfg = load_config()
    accounts = [a for a in cfg.get("accounts", []) if a.get("enabled", True)]
    if not accounts:
        logger.warning("未配置任何已启用的签到账号")
        return []

    logger.info("=== 开始批量执行癫影签到 (共 %d 个账号, 手动=%s) ===", len(accounts), is_manual)
    results = []

    for acc in accounts:
        try:
            res = execute_account_checkin(acc, is_manual=is_manual)
            results.append(res)
        except Exception as e:
            logger.error("执行账号 %s 发生未捕获异常: %s", acc.get("name"), e)
        time.sleep(1) # Interval between accounts

    # 组装合并 Telegram 卡片通知
    if len(results) == 1:
        r = results[0]
        award = r.get("award")
        already = "已签到" in r.get("message", "")
        award_str = f"{award:+d} 积分" if isinstance(award, int) and award != 0 else "无变动" if already else "0 积分"
        tg_title = "🎬 <b>癫影签到提示 ℹ️</b>" if already else ("🎬 <b>癫影签到成功 🎉</b>" if r.get("success") else "🎬 <b>癫影签到异常 ⚠️</b>")
        tg_text = (
            f"<b>👤 账号:</b> <code>{r.get('username', r.get('account_name'))}</code>\n"
            f"<b>🎯 模式:</b> {r.get('mode')}\n"
            f"<b>📊 结果:</b> <code>{r.get('message')}</code>\n"
            f"<b>💰 获得奖励:</b> <b>{award_str}</b>\n"
            f"<b>💎 当前剩余积分:</b> <b>{r.get('points')} 积分</b>\n"
            f"<b>📅 连续签到:</b> <b>{r.get('streak', 0)} 天</b>\n\n"
            f"⏰ <i>下次执行时间: 每天 {cfg.get('checkin_time', '00:05')}</i>"
        )
        send_tg_notification(tg_title, tg_text)
    elif len(results) > 1:
        tg_title = f"🎬 <b>癫影多账号自动签到汇总报告 ({len(results)}个账号) 🎉</b>"
        items_text = []
        for idx, r in enumerate(results, 1):
            award = r.get("award")
            already = "已签到" in r.get("message", "")
            award_str = f"{award:+d}" if isinstance(award, int) and award != 0 else ("0" if not already else "-")
            status_icon = "✅" if r.get("success") else "❌"
            items_text.append(
                f"<b>{idx}. {r.get('account_name', '账号')}</b> ({r.get('username')})\n"
                f"   {status_icon} <code>{r.get('message')}</code> (奖励: <b>{award_str}</b>)\n"
                f"   💰 剩余积分: <b>{r.get('points')}</b> | 连续: <b>{r.get('streak', 0)}天</b>"
            )
        tg_text = "\n\n".join(items_text) + f"\n\n⏰ <i>下次执行时间: 每天 {cfg.get('checkin_time', '00:05')}</i>"
        send_tg_notification(tg_title, tg_text)

    return results

# Scheduler loop
def scheduler_loop():
    logger.info("Scheduler thread started with multi-account schedule support.")
    account_last_run = {} # acc_id -> "YYYY-MM-DD"
    while True:
        try:
            cfg = load_config()
            global_time = cfg.get("checkin_time", "00:05").strip()
            now = datetime.now()
            now_time_str = now.strftime("%H:%M")
            today_str = now.strftime("%Y-%m-%d")

            for acc in cfg.get("accounts", []):
                if not acc.get("enabled", True):
                    continue
                acc_id = acc.get("id")
                target_time = (acc.get("checkin_time") or "").strip() or global_time
                if now_time_str == target_time and account_last_run.get(acc_id) != today_str:
                    logger.info("Hit scheduled checkin time %s for account %s on %s", target_time, acc.get("name"), today_str)
                    account_last_run[acc_id] = today_str
                    res = execute_account_checkin(acc, is_manual=False)

                    # 发送单账号定时签到卡片推送
                    award = res.get("award")
                    already = "已签到" in res.get("message", "")
                    award_str = f"{award:+d} 积分" if isinstance(award, int) and award != 0 else "无变动" if already else "0 积分"
                    tg_title = "🎬 <b>癫影签到提示 ℹ️</b>" if already else ("🎬 <b>癫影签到成功 🎉</b>" if res.get("success") else "🎬 <b>癫影签到异常 ⚠️</b>")
                    tg_text = (
                        f"<b>👤 账号:</b> <code>{res.get('username', res.get('account_name'))}</code>\n"
                        f"<b>🎯 模式:</b> {res.get('mode')}\n"
                        f"<b>📊 结果:</b> <code>{res.get('message')}</code>\n"
                        f"<b>💰 获得奖励:</b> <b>{award_str}</b>\n"
                        f"<b>💎 当前剩余积分:</b> <b>{res.get('points')} 积分</b>\n"
                        f"<b>📅 连续签到:</b> <b>{res.get('streak', 0)} 天</b>\n\n"
                        f"⏰ <i>此账号定时时间: 每天 {target_time}</i>"
                    )
                    send_tg_notification(tg_title, tg_text)
        except Exception as e:
            logger.error("Scheduler loop error: %s", e)
        time.sleep(30)

app = FastAPI(title="DianYing Multi-Account Checkin", description="癫影多账号聚合自动签到中心")

@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=scheduler_loop, daemon=True)
    t.start()
    cfg = load_config()
    if cfg.get("run_on_start") and cfg.get("accounts"):
        threading.Thread(target=lambda: (time.sleep(2), execute_all_checkin(is_manual=False)), daemon=True).start()

@app.get("/api/status")
def api_status():
    cfg = load_config()
    history = load_history()
    today_str = datetime.now().strftime("%Y-%m-%d")

    accounts_status = []
    for acc in cfg.get("accounts", []):
        acc_id = acc.get("id")
        cli = get_client_for_account(acc)
        uinfo = None
        if acc.get("cookie") or (acc.get("email") and acc.get("password")):
            try:
                uinfo = cli.get_account_info()
            except Exception as e:
                uinfo = {"success": False, "authenticated": False, "message": str(e)}

        checked_in_today = any(
            h.get("time", "").startswith(today_str)
            and h.get("success")
            and (h.get("account_id") == acc_id or h.get("username") == (uinfo.get("username") if uinfo else None))
            for h in history
        )

        safe_acc = {
            "id": acc_id,
            "name": acc.get("name") or acc.get("email", ""),
            "email": acc.get("email", ""),
            "has_password": bool(acc.get("password")),
            "checkin_mode": acc.get("checkin_mode", "lucky"),
            "checkin_time": (acc.get("checkin_time") or "").strip(),
            "enabled": acc.get("enabled", True),
            "user_info": uinfo,
            "checked_in_today": checked_in_today,
        }
        accounts_status.append(safe_acc)

    return {
        "ok": True,
        "accounts": accounts_status,
        "global_config": {
            "checkin_time": cfg.get("checkin_time", "00:05"),
            "tg_bot_token": cfg.get("tg_bot_token", ""),
            "tg_chat_id": cfg.get("tg_chat_id", ""),
            "tg_base_url": cfg.get("tg_base_url", "https://api.telegram.org"),
            "run_on_start": cfg.get("run_on_start", True)
        },
        "history": history[:30]
    }

@app.post("/api/accounts")
def api_save_account(data: dict):
    cfg = load_config()
    accounts = cfg.get("accounts", [])
    acc_id = data.get("id") or f"acc_{uuid.uuid4().hex[:8]}"

    existing_idx = next((i for i, a in enumerate(accounts) if a.get("id") == acc_id), None)
    
    if existing_idx is not None:
        target = accounts[existing_idx]
        target["name"] = data.get("name") or target.get("name")
        target["email"] = data.get("email") or target.get("email")
        if data.get("password") and data["password"].strip():
            target["password"] = data["password"].strip()
        if "cookie" in data and data["cookie"].strip():
            target["cookie"] = data["cookie"].strip()
        target["checkin_mode"] = data.get("checkin_mode", target.get("checkin_mode", "lucky"))
        target["checkin_time"] = (data.get("checkin_time") or "").strip()
        target["enabled"] = bool(data.get("enabled", target.get("enabled", True)))
    else:
        target = {
            "id": acc_id,
            "name": data.get("name") or (data.get("email", "").split("@")[0] if data.get("email") else "新账号"),
            "email": data.get("email", "").strip(),
            "password": data.get("password", "").strip(),
            "cookie": data.get("cookie", "").strip(),
            "checkin_mode": data.get("checkin_mode", "lucky"),
            "checkin_time": (data.get("checkin_time") or "").strip(),
            "enabled": bool(data.get("enabled", True))
        }
        accounts.append(target)

    # Validate / login immediately if email & password provided
    cli = get_client_for_account(target)
    if target.get("email") and target.get("password"):
        login_res = cli.login()
        if login_res.get("success") and cli._cookie_str:
            target["cookie"] = cli._cookie_str

    cfg["accounts"] = accounts
    save_config(cfg)
    return {"ok": True, "account_id": acc_id}

@app.delete("/api/accounts/{account_id}")
def api_delete_account(account_id: str):
    cfg = load_config()
    accounts = [a for a in cfg.get("accounts", []) if a.get("id") != account_id]
    cfg["accounts"] = accounts
    save_config(cfg)
    with client_pool_lock:
        if account_id in _account_clients:
            del _account_clients[account_id]
    return {"ok": True}

@app.post("/api/checkin")
def api_checkin(data: dict = None):
    data = data or {}
    acc_id = data.get("account_id")
    if acc_id:
        cfg = load_config()
        acc = next((a for a in cfg.get("accounts", []) if a.get("id") == acc_id), None)
        if not acc:
            raise HTTPException(status_code=404, detail="Account not found")
        res = execute_account_checkin(acc, is_manual=True)
        return {"ok": True, "results": [res]}
    else:
        results = execute_all_checkin(is_manual=True)
        return {"ok": True, "results": results}

@app.post("/api/config")
def api_save_global_config(data: dict):
    cfg = load_config()
    for k in ["checkin_time", "tg_bot_token", "tg_chat_id", "tg_base_url", "run_on_start"]:
        if k in data:
            cfg[k] = data[k]
    save_config(cfg)
    return {"ok": True, "global_config": data}

@app.post("/api/test-tg")
def api_test_tg():
    send_tg_notification(
        "🎬 <b>癫影 Telegram 连通性测试</b> ✅",
        f"<b>状态:</b> 连通成功！\n<b>测试时间:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return {"ok": True, "msg": "测试消息已发出，请在 Telegram 查看"}

HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>🎬 癫影多账号自动签到中心</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/vue@3/dist/vue.global.js"></script>
  <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
  <style>
    body { background: radial-gradient(circle at top, #1e1b4b 0%, #09090b 100%); color: #f4f4f5; font-family: system-ui, -apple-system, sans-serif; min-height: 100vh; }
    .glass { background: rgba(24, 24, 27, 0.75); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 1rem; }
    .glass-card { background: rgba(39, 39, 42, 0.5); border: 1px solid rgba(255, 255, 255, 0.05); }
    [v-cloak] { display: none; }
  </style>
</head>
<body class="p-4 md:p-8">
  <div id="app" v-cloak class="max-w-5xl mx-auto space-y-6">
    <!-- Header -->
    <header class="glass p-6 flex flex-col md:flex-row items-center justify-between gap-4 shadow-2xl">
      <div class="flex items-center gap-4">
        <div class="w-14 h-14 rounded-2xl bg-indigo-500/20 border border-indigo-500/30 flex items-center justify-center text-3xl text-indigo-400 shadow-inner">
          🎬
        </div>
        <div>
          <div class="flex items-center gap-3">
            <h1 class="text-2xl font-bold bg-gradient-to-r from-indigo-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">癫影多账号自动签到</h1>
            <span class="px-2.5 py-0.5 text-xs font-bold rounded-full bg-indigo-500/20 text-indigo-400 border border-indigo-500/30">
              {{ accounts.length }} 个账号
            </span>
          </div>
          <p class="text-xs text-zinc-400 mt-1">支持多账号聚合 · 独立 ECDSA 签名与静默续期 · Telegram 合并汇报卡片</p>
        </div>
      </div>
      <div class="flex items-center gap-3 flex-wrap">
        <button @click="openAddModal" class="px-4 py-2.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 border border-zinc-600 rounded-xl transition-all flex items-center gap-2 text-sm font-medium">
          <i class="fa-solid fa-plus text-indigo-400"></i>
          <span>添加账号</span>
        </button>
        <button @click="checkinAll" :disabled="checkingAll" class="px-5 py-2.5 bg-gradient-to-r from-indigo-500 to-purple-600 hover:from-indigo-600 hover:to-purple-700 text-white font-medium rounded-xl shadow-lg transition-all active:scale-95 disabled:opacity-50 flex items-center gap-2 text-sm">
          <i class="fa-solid fa-bolt" :class="{'fa-spin': checkingAll}"></i>
          <span>全部立刻签到</span>
        </button>
        <button @click="loadData" class="p-2.5 bg-zinc-800 hover:bg-zinc-700 rounded-xl border border-zinc-700 text-zinc-300 transition-all">
          <i class="fa-solid fa-arrows-rotate" :class="{'fa-spin': refreshing}"></i>
        </button>
      </div>
    </header>

    <!-- Accounts Grid -->
    <div class="space-y-3">
      <div class="flex items-center justify-between px-1">
        <h2 class="text-sm font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
          <i class="fa-solid fa-users text-indigo-400"></i> 已绑定账号列表
        </h2>
        <span class="text-xs text-zinc-500">定时时间: 每天 {{ globalConfig.checkin_time || '00:05' }}</span>
      </div>

      <div v-if="!accounts.length" class="glass p-12 text-center space-y-4">
        <div class="text-4xl">📭</div>
        <div class="text-zinc-400">暂未添加任何癫影账号</div>
        <button @click="openAddModal" class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-sm font-medium">
          立即添加第一个账号
        </button>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div v-for="acc in accounts" :key="acc.id" class="glass p-5 space-y-4 relative overflow-hidden transition-all hover:border-indigo-500/40">
          <!-- Top Row -->
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-3">
              <div class="w-12 h-12 rounded-full bg-indigo-950/80 border border-indigo-500/30 flex items-center justify-center font-bold text-lg text-indigo-400 overflow-hidden shrink-0">
                <img v-if="acc.user_info && acc.user_info.avatar" :src="acc.user_info.avatar" class="w-full h-full object-cover">
                <span v-else>{{ (acc.name || acc.email || 'U')[0].toUpperCase() }}</span>
              </div>
              <div>
                <div class="font-bold text-zinc-100 flex items-center gap-2">
                  <span>{{ acc.name }}</span>
                  <span v-if="acc.user_info && acc.user_info.is_vip" class="px-2 py-0.5 text-[10px] font-bold rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">VIP</span>
                </div>
                <div class="text-xs text-zinc-400 font-mono">{{ acc.email || '未填邮箱' }}</div>
              </div>
            </div>

            <!-- Tags -->
            <div class="flex flex-col items-end gap-1.5">
              <span v-if="acc.checked_in_today" class="px-2 py-0.5 text-[11px] font-bold rounded-full bg-emerald-500/20 text-emerald-400 border border-emerald-500/30">
                ✅ 今日已签到
              </span>
              <span v-else class="px-2 py-0.5 text-[11px] font-bold rounded-full bg-amber-500/20 text-amber-400 border border-amber-500/30">
                ⏳ 今日未签到
              </span>
              <span class="text-[11px] text-zinc-400">
                {{ acc.checkin_mode === 'lucky' ? '🎲 运气模式' : '📅 普通模式' }} · ⏰ {{ acc.checkin_time || ('跟随全局 ' + (globalConfig.checkin_time || '00:05')) }}
              </span>
            </div>
          </div>

          <!-- Account Data Stats -->
          <div class="grid grid-cols-3 gap-2 p-3 bg-zinc-900/60 rounded-xl border border-zinc-800/80 text-center">
            <div>
              <div class="text-[11px] text-zinc-500">剩余积分</div>
              <div class="text-lg font-bold text-emerald-400">
                {{ acc.user_info && acc.user_info.points !== undefined ? acc.user_info.points : '-' }}
              </div>
            </div>
            <div>
              <div class="text-[11px] text-zinc-500">连续签到</div>
              <div class="text-lg font-semibold text-zinc-200">
                {{ acc.user_info && acc.user_info.consecutive_signin ? acc.user_info.consecutive_signin : 0 }} <span class="text-xs font-normal">天</span>
              </div>
            </div>
            <div>
              <div class="text-[11px] text-zinc-500">自动续期</div>
              <div class="text-sm font-semibold mt-1">
                <span v-if="acc.has_password" class="text-emerald-400" title="已开启账号密码静默续期"><i class="fa-solid fa-shield-halved"></i> 守护中</span>
                <span v-else class="text-zinc-500 text-xs">仅Cookie</span>
              </div>
            </div>
          </div>

          <!-- Bottom Actions -->
          <div class="flex items-center justify-between pt-1 text-xs">
            <div class="text-zinc-500">
              <span v-if="acc.user_info && acc.user_info.vip_until">VIP至: {{ acc.user_info.vip_until.split('T')[0] }}</span>
              <span v-else-if="acc.user_info && !acc.user_info.authenticated" class="text-rose-400">
                {{ acc.user_info.message || '认证失效' }}
              </span>
            </div>
            <div class="flex items-center gap-2">
              <button @click="checkinSingle(acc)" :disabled="actionLoading[acc.id]" class="px-3 py-1.5 bg-indigo-600/30 hover:bg-indigo-600/50 text-indigo-300 border border-indigo-500/30 rounded-lg transition-all flex items-center gap-1.5">
                <i class="fa-solid fa-bolt" :class="{'fa-spin': actionLoading[acc.id]}"></i>
                <span>签到</span>
              </button>
              <button @click="openEditModal(acc)" class="px-2.5 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 border border-zinc-700 rounded-lg transition-all">
                <i class="fa-solid fa-pen-to-square"></i>
              </button>
              <button @click="deleteAccount(acc)" class="px-2.5 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 border border-rose-500/20 rounded-lg transition-all">
                <i class="fa-solid fa-trash-can"></i>
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Global Settings -->
    <div class="glass p-6 space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-sm font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
          <i class="fa-solid fa-gear text-indigo-400"></i> 定时任务与 Telegram 通知配置
        </h2>
        <button @click="testTelegram" :disabled="testingTg" class="text-xs px-3 py-1.5 bg-sky-500/20 hover:bg-sky-500/30 text-sky-300 border border-sky-500/30 rounded-lg transition-all flex items-center gap-1.5">
          <i class="fa-solid fa-paper-plane" :class="{'fa-spin': testingTg}"></i>
          <span>测试 Telegram 推送</span>
        </button>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
        <div>
          <label class="block text-xs text-zinc-400 mb-1">每日自动签到时间</label>
          <input type="text" v-model="globalConfig.checkin_time" placeholder="00:05" class="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2.5 text-zinc-200 font-mono text-xs">
        </div>
        <div>
          <label class="block text-xs text-zinc-400 mb-1">Telegram Bot Token</label>
          <input type="text" v-model="globalConfig.tg_bot_token" placeholder="1234567890:AAE..." class="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2.5 text-zinc-200 font-mono text-xs">
        </div>
        <div>
          <label class="block text-xs text-zinc-400 mb-1">Telegram Chat ID</label>
          <input type="text" v-model="globalConfig.tg_chat_id" placeholder="123456789" class="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2.5 text-zinc-200 font-mono text-xs">
        </div>
      </div>

      <div class="flex justify-end pt-2">
        <button @click="saveGlobalConfig" :disabled="savingGlobal" class="px-6 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-medium rounded-xl shadow-lg transition-all text-sm flex items-center gap-2">
          <i class="fa-solid fa-floppy-disk" :class="{'fa-spin': savingGlobal}"></i>
          <span>保存全局配置</span>
        </button>
      </div>
    </div>

    <!-- History -->
    <div class="glass p-6 space-y-4">
      <div class="flex items-center justify-between">
        <h2 class="text-sm font-semibold text-zinc-400 uppercase tracking-wider flex items-center gap-2">
          <i class="fa-solid fa-clock-rotate-left text-indigo-400"></i> 签到历史明细 (最近 30 次)
        </h2>
      </div>
      <div class="overflow-x-auto">
        <table class="w-full text-left text-sm text-zinc-300">
          <thead class="text-xs uppercase bg-zinc-900/60 text-zinc-400">
            <tr>
              <th class="px-4 py-3 rounded-l-xl">执行时间</th>
              <th class="px-4 py-3">账号</th>
              <th class="px-4 py-3">模式</th>
              <th class="px-4 py-3">状态/响应</th>
              <th class="px-4 py-3">积分奖励</th>
              <th class="px-4 py-3 rounded-r-xl">剩余积分</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-zinc-800">
            <tr v-for="h in history" :key="h.time + h.account_name" class="hover:bg-zinc-800/30 transition-colors">
              <td class="px-4 py-3 font-mono text-xs text-zinc-400">{{ h.time }}</td>
              <td class="px-4 py-3 font-medium text-zinc-200">{{ h.account_name || h.username }}</td>
              <td class="px-4 py-3">
                <span class="px-2 py-0.5 text-xs rounded-full" :class="h.mode && h.mode.includes('运气') ? 'bg-pink-500/20 text-pink-300' : 'bg-blue-500/20 text-blue-300'">
                  {{ h.mode || '自动' }}
                </span>
              </td>
              <td class="px-4 py-3">
                <span :class="h.success ? 'text-emerald-400' : 'text-rose-400'" class="font-medium">
                  {{ h.message }}
                </span>
              </td>
              <td class="px-4 py-3 font-bold" :class="h.award > 0 ? 'text-amber-400' : (h.award < 0 ? 'text-rose-400' : 'text-zinc-400')">
                {{ h.award !== undefined ? (h.award > 0 ? '+' + h.award : h.award) : '-' }}
              </td>
              <td class="px-4 py-3 text-emerald-400 font-semibold">{{ h.points ?? '-' }}</td>
            </tr>
            <tr v-if="!history.length">
              <td colspan="6" class="text-center py-8 text-zinc-500 text-sm">暂无签到历史记录</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Add/Edit Account Modal -->
    <div v-if="showModal" class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4">
      <div class="glass w-full max-w-lg p-6 space-y-4 border border-zinc-700 shadow-2xl relative">
        <div class="flex items-center justify-between pb-2 border-b border-zinc-800">
          <h3 class="text-lg font-bold text-zinc-100 flex items-center gap-2">
            <i class="fa-solid fa-user-plus text-indigo-400"></i>
            <span>{{ modalForm.id ? '编辑癫影账号' : '添加癫影账号' }}</span>
          </h3>
          <button @click="showModal = false" class="text-zinc-400 hover:text-zinc-200">
            <i class="fa-solid fa-xmark text-lg"></i>
          </button>
        </div>

        <div class="space-y-3.5 text-sm">
          <div>
            <label class="block text-xs font-medium text-zinc-300 mb-1">账号备注名 (必填)</label>
            <input type="text" v-model="modalForm.name" placeholder="例如：主账号 / 小号" class="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2.5 text-zinc-200 text-xs">
          </div>

          <!-- Silent Login Form -->
          <div class="p-3 bg-indigo-950/30 border border-indigo-500/20 rounded-xl space-y-2.5">
            <div class="font-semibold text-xs text-indigo-300 flex items-center gap-1.5">
              <i class="fa-solid fa-shield-halved text-emerald-400"></i>
              <span>账号密码静默续期（推荐 · 永不过期）</span>
            </div>
            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              <div>
                <label class="block text-[11px] text-zinc-400 mb-1">注册邮箱 (Email)</label>
                <input type="email" v-model="modalForm.email" placeholder="youremail@qq.com" class="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2 text-zinc-200 text-xs">
              </div>
              <div>
                <label class="block text-[11px] text-zinc-400 mb-1">登录密码 (Password)</label>
                <input type="password" v-model="modalForm.password" :placeholder="modalForm.id ? '留空则保持原密码' : '输入密码'" class="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2 text-zinc-200 text-xs">
              </div>
            </div>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
            <div>
              <label class="block text-xs font-medium text-zinc-300 mb-1">签到模式</label>
              <select v-model="modalForm.checkin_mode" class="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2.5 text-zinc-200 text-xs">
                <option value="lucky">🎲 运气签到模式 (推荐)</option>
                <option value="normal">📅 普通稳健模式</option>
              </select>
            </div>
            <div>
              <label class="block text-xs font-medium text-zinc-300 mb-1">⏰ 独立每日签到时间</label>
              <input type="text" v-model="modalForm.checkin_time" placeholder="例如 08:30 (留空跟随全局)" class="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2.5 text-zinc-200 text-xs font-mono">
            </div>
          </div>

          <div>
            <label class="block text-xs font-medium text-zinc-300 mb-1">手动指定 Cookie (可选备用)</label>
            <textarea v-model="modalForm.cookie" rows="2" placeholder="填了账号密码后系统会自动获取并维护 Cookie，此处可留空..." class="w-full bg-zinc-900 border border-zinc-700 rounded-xl p-2 text-zinc-200 font-mono text-xs"></textarea>
          </div>

          <div class="flex items-center gap-2 pt-1">
            <input type="checkbox" id="acc-enabled" v-model="modalForm.enabled" class="rounded bg-zinc-900 border-zinc-700 text-indigo-600 focus:ring-0">
            <label for="acc-enabled" class="text-xs text-zinc-300 select-none">启用此账号自动签到</label>
          </div>
        </div>

        <div class="flex justify-end gap-3 pt-3 border-t border-zinc-800">
          <button @click="showModal = false" class="px-4 py-2 bg-zinc-800 hover:bg-zinc-700 text-zinc-300 rounded-xl text-xs">取消</button>
          <button @click="saveAccount" :disabled="savingAccount" class="px-5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-medium flex items-center gap-1.5">
            <i class="fa-solid fa-check" :class="{'fa-spin': savingAccount}"></i>
            <span>保存账号</span>
          </button>
        </div>
      </div>
    </div>
  </div>

  <script>
    const { createApp, ref, reactive, onMounted } = Vue;
    createApp({
      setup() {
        const refreshing = ref(false);
        const checkingAll = ref(false);
        const savingGlobal = ref(false);
        const testingTg = ref(false);
        const savingAccount = ref(false);
        const actionLoading = reactive({});

        const accounts = ref([]);
        const history = ref([]);
        const globalConfig = reactive({
          checkin_time: '00:05',
          tg_bot_token: '',
          tg_chat_id: '',
          tg_base_url: 'https://api.telegram.org',
          run_on_start: true
        });

        // Modal
        const showModal = ref(false);
        const modalForm = reactive({
          id: '',
          name: '',
          email: '',
          password: '',
          cookie: '',
          checkin_mode: 'lucky',
          checkin_time: '',
          enabled: true
        });

        const loadData = async () => {
          refreshing.value = true;
          try {
            const res = await fetch('/api/status');
            const d = await res.json();
            if (d.ok) {
              accounts.value = d.accounts || [];
              history.value = d.history || [];
              if (d.global_config) {
                Object.assign(globalConfig, d.global_config);
              }
            }
          } catch(e) {
            console.error(e);
          } finally {
            refreshing.value = false;
          }
        };

        const openAddModal = () => {
          modalForm.id = '';
          modalForm.name = '';
          modalForm.email = '';
          modalForm.password = '';
          modalForm.cookie = '';
          modalForm.checkin_mode = 'lucky';
          modalForm.checkin_time = '';
          modalForm.enabled = true;
          showModal.value = true;
        };

        const openEditModal = (acc) => {
          modalForm.id = acc.id;
          modalForm.name = acc.name || '';
          modalForm.email = acc.email || '';
          modalForm.password = '';
          modalForm.cookie = '';
          modalForm.checkin_mode = acc.checkin_mode || 'lucky';
          modalForm.checkin_time = acc.checkin_time || '';
          modalForm.enabled = acc.enabled !== false;
          showModal.value = true;
        };

        const saveAccount = async () => {
          if (!modalForm.name) {
            alert('请填写账号备注名');
            return;
          }
          savingAccount.value = true;
          try {
            const res = await fetch('/api/accounts', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(modalForm)
            });
            const d = await res.json();
            if (d.ok) {
              showModal.value = false;
              await loadData();
            } else {
              alert('保存失败: ' + (d.detail || '未知错误'));
            }
          } catch(e) {
            alert('请求异常: ' + e.message);
          } finally {
            savingAccount.value = false;
          }
        };

        const deleteAccount = async (acc) => {
          if (!confirm(`确认删除账号 "${acc.name}" 吗？`)) return;
          try {
            const res = await fetch(`/api/accounts/${acc.id}`, { method: 'DELETE' });
            const d = await res.json();
            if (d.ok) {
              await loadData();
            }
          } catch(e) {
            alert('删除失败: ' + e.message);
          }
        };

        const checkinSingle = async (acc) => {
          actionLoading[acc.id] = true;
          try {
            const res = await fetch('/api/checkin', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ account_id: acc.id })
            });
            const d = await res.json();
            const r = (d.results && d.results[0]) || {};
            alert(`${acc.name}: ${r.message || '签到已执行'}`);
            await loadData();
          } catch(e) {
            alert('签到失败: ' + e.message);
          } finally {
            actionLoading[acc.id] = false;
          }
        };

        const checkinAll = async () => {
          checkingAll.value = true;
          try {
            const res = await fetch('/api/checkin', { method: 'POST' });
            const d = await res.json();
            alert(`已执行全部账号签到 (共 ${d.results ? d.results.length : 0} 个)`);
            await loadData();
          } catch(e) {
            alert('批量签到失败: ' + e.message);
          } finally {
            checkingAll.value = false;
          }
        };

        const saveGlobalConfig = async () => {
          savingGlobal.value = true;
          try {
            const res = await fetch('/api/config', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify(globalConfig)
            });
            const d = await res.json();
            if (d.ok) {
              alert('全局配置保存成功！');
              await loadData();
            }
          } catch(e) {
            alert('保存失败: ' + e.message);
          } finally {
            savingGlobal.value = false;
          }
        };

        const testTelegram = async () => {
          testingTg.value = true;
          try {
            await saveGlobalConfig();
            const res = await fetch('/api/test-tg', { method: 'POST' });
            const d = await res.json();
            alert(d.msg || '测试通知已发出');
          } catch(e) {
            alert('测试失败: ' + e.message);
          } finally {
            testingTg.value = false;
          }
        };

        onMounted(() => {
          loadData();
        });

        return {
          refreshing, checkingAll, savingGlobal, testingTg, savingAccount, actionLoading,
          accounts, history, globalConfig, showModal, modalForm,
          loadData, openAddModal, openEditModal, saveAccount, deleteAccount, checkinSingle, checkinAll,
          saveGlobalConfig, testTelegram
        };
      }
    }).mount('#app');
  </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def index():
    return HTML_PAGE

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
