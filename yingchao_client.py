import os
import sys
import json
import time
import base64
import logging
import subprocess
import threading
from pathlib import Path
import requests

logger = logging.getLogger("yingchao_client")

class YingChaoClient:
    BASE_URL = "https://re0.me"
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    def __init__(self, token: str = "", cookie: str = "", proxy: str = ""):
        self._token = ""
        self._cookie_str = ""
        self._user_id = "0"
        self._proxy = str(proxy or os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY") or "").strip()
        
        self._session = requests.Session()
        self.set_proxy(self._proxy)
        
        # State
        self._signer_proc = None
        self._signer_lock = threading.Lock()
        self._handshake_session = None # {cid, server_pub, expires_at}
        
        raw_auth = str(cookie or token or "").strip()
        if raw_auth:
            self.set_cookie(raw_auth)

    def set_proxy(self, proxy: str):
        self._proxy = str(proxy or "").strip()
        if self._proxy:
            self._session.proxies = {"http": self._proxy, "https": self._proxy}
        else:
            self._session.proxies = {}

    @staticmethod
    def _parse_jwt_payload(jwt_str: str) -> dict:
        try:
            parts = jwt_str.strip().split(".")
            if len(parts) >= 2:
                payload_b64 = parts[1]
                # Fix padding
                payload_b64 += "=" * ((4 - len(payload_b64) % 4) % 4)
                # urlsafe base64 decode
                decoded = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
                return json.loads(decoded.decode("utf-8"))
        except Exception as e:
            logger.debug("Failed to decode JWT payload: %s", e)
        return {}

    def set_cookie(self, cookie_str: str):
        clean = str(cookie_str or "").strip()
        self._cookie_str = clean
        self._token = ""
        self._user_id = "0"
        if not clean:
            return

        # Check if entire string is just the raw token or api_key (no ; or =)
        if ";" not in clean and "=" not in clean:
            self._token = clean
        else:
            # Parse key=value pairs
            parts = [p.strip() for p in clean.split(";") if p.strip()]
            for p in parts:
                if "=" in p:
                    k, v = p.split("=", 1)
                    k, v = k.strip(), v.strip()
                    if k in ("token", "hdh_token", "session_token", "api_key", "apiKey", "apikey"):
                        self._token = v
                    elif k == "hdh_uid" and v.isdigit():
                        self._user_id = v

        # If user_id not explicitly in hdh_uid, extract from JWT token
        if self._token:
            payload = self._parse_jwt_payload(self._token)
            uid = payload.get("user_id") or payload.get("sub") or payload.get("id")
            if uid:
                self._user_id = str(uid)

        logger.info("影巢客户端已配置认证信息 (用户ID: %s, Token长度: %d)", self._user_id, len(self._token))

    def _ensure_signer(self):
        with self._signer_lock:
            if self._signer_proc and self._signer_proc.poll() is None:
                return

            candidates = [
                Path(__file__).parent / "yingchao_signer.js",
                Path("/app/yingchao_signer.js"),
                Path.cwd() / "yingchao_signer.js"
            ]
            signer_script = next((str(p) for p in candidates if p.exists()), None)
            if not signer_script:
                raise RuntimeError("yingchao_signer.js not found")

            logger.info("启动影巢 WASM 算力守护进程: %s", signer_script)
            self._signer_proc = subprocess.Popen(
                ["node", signer_script],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(Path(signer_script).parent)
            )

    def _send_signer(self, cmd: dict) -> dict:
        self._ensure_signer()
        with self._signer_lock:
            try:
                line = json.dumps(cmd) + "\n"
                self._signer_proc.stdin.write(line)
                self._signer_proc.stdin.flush()
                res_line = self._signer_proc.stdout.readline()
                if not res_line:
                    raise RuntimeError("Signer process stdout closed unexpectedly")
                return json.loads(res_line.strip())
            except Exception as e:
                logger.error("通信或执行 WASM 算力模块异常: %s", e)
                if self._signer_proc:
                    try:
                        self._signer_proc.terminate()
                    except Exception:
                        pass
                    self._signer_proc = None
                raise

    def _ensure_session(self, force: bool = False):
        now = time.time()
        if not force and self._handshake_session:
            expires_at = self._handshake_session.get("expires_at", 0)
            if expires_at > now + 60:
                return

        logger.info("正在执行影巢安全会话握手与 PoW 求解...")
        init_res = self._send_signer({"action": "init_handshake", "userAgent": self.USER_AGENT})
        if not init_res.get("success"):
            raise RuntimeError(f"WASM 初始化握手失败: {init_res.get('error')}")

        payload = init_res["payload"]
        hs_url = f"{self.BASE_URL}/api/public/security/session/handshake"
        headers = {"User-Agent": self.USER_AGENT, "Content-Type": "application/json"}

        resp = self._session.post(hs_url, json=payload, headers=headers, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"影巢握手端点返回 HTTP {resp.status_code}: {resp.text[:200]}")

        data = resp.json()
        if not data.get("success") or not data.get("data"):
            raise RuntimeError(f"影巢握手拒绝: {data}")

        hs_data = data["data"]
        fin_res = self._send_signer({
            "action": "finalize_handshake",
            "cid": hs_data["cid"],
            "server_pub": hs_data["server_pub"],
            "expires_at": hs_data["expires_at"]
        })
        if not fin_res.get("success"):
            raise RuntimeError("WASM 完成握手失败")

        self._handshake_session = hs_data
        logger.info("影巢安全会话建立成功！CID: %s (有效期至: %s)", hs_data["cid"], hs_data.get("expires_at"))

    def request_json(self, method: str, api_path: str, data: dict = None, **kwargs) -> tuple:
        method = method.upper()
        body_str = json.dumps(data) if data and method != "GET" else ""

        for attempt in range(2):
            try:
                self._ensure_session(force=(attempt > 0))
                sign_res = self._send_signer({
                    "action": "sign",
                    "method": method,
                    "path": api_path,
                    "userId": self._user_id,
                    "body": body_str
                })

                if not sign_res.get("success"):
                    raise RuntimeError(f"生成签名异常: {sign_res.get('error')}")

                headers = {
                    "User-Agent": self.USER_AGENT,
                    "Accept": "application/json, text/plain, */*",
                }
                headers.update(sign_res["headers"])

                # Attach user cookies and authorization token / API Key
                if self._token:
                    headers["Authorization"] = f"Bearer {self._token}"
                    headers["X-API-Key"] = self._token
                    headers["Cookie"] = f"token={self._token}; hdh_uid={self._user_id}"
                elif self._cookie_str:
                    headers["Cookie"] = self._cookie_str

                if body_str:
                    headers["Content-Type"] = "application/json"

                url = f"{self.BASE_URL}{api_path}"
                resp = self._session.request(
                    method,
                    url,
                    headers=headers,
                    data=body_str.encode("utf-8") if body_str else None,
                    timeout=20,
                    **kwargs
                )

                # Check if session/signature expired
                if resp.status_code == 401 and any(code in resp.text for code in ("signature_invalid", "invalid_session", "session_user_mismatch")):
                    logger.warning("影巢安全会话或签名失效 (第%d次)，尝试重新握手...", attempt + 1)
                    self._handshake_session = None
                    continue

                try:
                    return resp.json(), resp.status_code
                except Exception:
                    return {"raw": resp.text[:300]}, resp.status_code

            except Exception as e:
                logger.error("影巢网络请求异常 [%s %s]: %s", method, api_path, e)
                if attempt == 1:
                    return {"error": str(e), "message": f"通信异常: {e}"}, 500
                time.sleep(1)

        return {"error": "request_failed"}, 500

    def get_account_info(self) -> dict:
        if not self._token and not self._cookie_str:
            return {"success": False, "authenticated": False, "message": "未配置影巢 Token 或 Cookie"}

        try:
            data, code = self.request_json("GET", "/api/customer/user/current")
            if code == 401 or data.get("code") == 401:
                return {"success": False, "authenticated": False, "message": data.get("message") or "Token/Cookie 已失效，请重新复制"}

            if code == 200 and (data.get("success") or data.get("data")):
                user = data.get("data") or data
                username = user.get("username") or user.get("nickname") or f"影巢用户_{self._user_id}"
                points = user.get("points") if user.get("points") is not None else user.get("score", 0)
                streak = user.get("sign_in_days") or user.get("consecutive_signin") or user.get("streak", 0)
                is_vip = bool(user.get("vip") or user.get("is_vip"))
                vip_until = user.get("vip_expired_at") or user.get("vip_until") or ""

                return {
                    "success": True,
                    "authenticated": True,
                    "username": username,
                    "email": user.get("email", ""),
                    "points": points,
                    "is_vip": is_vip,
                    "vip_until": vip_until,
                    "consecutive_signin": streak,
                    "avatar": user.get("avatar_url") or user.get("avatar") or "",
                    "cookie": self._cookie_str or self._token,
                    "user_id": self._user_id
                }

            msg = str(data.get("message") or data.get("msg") or f"HTTP {code}")
            return {"success": False, "authenticated": False, "message": msg}
        except Exception as e:
            return {"success": False, "authenticated": False, "message": f"查询用户信息异常: {e}"}

    def signin(self, mode: str = "normal") -> dict:
        is_gambler = (mode == "gambler")
        mode_label = "gambler" if is_gambler else "normal"

        acct = self.get_account_info()
        if not acct.get("authenticated"):
            return {
                "success": False,
                "already_checked_in": False,
                "message": acct.get("message") or "影巢账号未登录或凭证失效",
                "mode": mode_label
            }

        payload = {"is_gambler": is_gambler}
        data, code = self.request_json("POST", "/api/customer/user/checkin", data=payload)

        msg = str(data.get("message") or data.get("msg") or data.get("description") or "")
        logger.info("影巢签到返回 (HTTP %s): %s", code, data)

        already = (
            data.get("code") == "already_signed"
            or "已签到" in msg
            or "今日已签" in msg
            or "无需重复" in msg
        )

        if already:
            return {
                "success": True,
                "already_checked_in": True,
                "message": "今日已签到",
                "mode": mode_label,
                "award": 0
            }

        if code == 200 and (data.get("success") or data.get("code") in (200, "200", "ok", 0)):
            res_data = data.get("data") if isinstance(data.get("data"), dict) else {}
            award = res_data.get("award") or res_data.get("points") or data.get("award")
            return {
                "success": True,
                "already_checked_in": False,
                "message": msg or "签到成功",
                "mode": mode_label,
                "award": award,
                "streak": res_data.get("streak") or res_data.get("sign_in_days") or 1
            }

        return {
            "success": False,
            "already_checked_in": False,
            "message": msg or f"签到异常 (HTTP {code})",
            "mode": mode_label
        }

    def __del__(self):
        if self._signer_proc:
            try:
                self._signer_proc.terminate()
            except Exception:
                pass
