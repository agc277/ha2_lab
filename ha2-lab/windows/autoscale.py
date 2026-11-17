"""自動擴展／縮減：接收 Alertmanager 的告警，自動執行 scale_out.py 或 scale_in.py。

  BackendQueueHigh（排隊過多） → python scale_out.py
  BackendIdle（流量低）         → python scale_in.py

使用方式（Windows cmd，與 scale_out.py 放在同一個資料夾）：
    set HA2_GUEST_PASS=範本機root密碼
    set HA2_DISCORD_WEBHOOK=https://discord.com/api/webhooks/...   （選用：把動作通知到 Discord）
    python autoscale.py
需求：Windows 防火牆允許 192.168.20.5 連到 TCP 9095。
"""
import getpass
import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from clone_vms import BASE

PORT = 9095
ALLOW = {"192.168.20.5", "127.0.0.1"}   # 只接受 ctl（Alertmanager）
COOLDOWN = 180                          # 每次動作完成後，至少隔 180 秒才做下一次
ACTIONS = {"BackendQueueHigh": "out", "BackendIdle": "in"}
HERE = Path(__file__).resolve().parent

lock = threading.Lock()
last_done = 0.0


def log(msg):
    print(f"{datetime.now():%H:%M:%S} {msg}", flush=True)


def discord(msg):
    url = os.environ.get("HA2_DISCORD_WEBHOOK")
    if not url:
        return
    req = urllib.request.Request(
        url, data=json.dumps({"content": msg}).encode(),
        headers={"Content-Type": "application/json", "User-Agent": "HA2-autoscale/1.0"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:  # 通知失敗不影響擴展
        log(f"Discord 通知失敗：{e}")


def scaled():
    """app-3 的 VM 存在，就當作目前是擴展狀態。"""
    return (BASE / "app-3" / "app-3.vmx").exists()


def run(action):
    global last_done
    zh = "擴展" if action == "out" else "縮減"
    if not lock.acquire(blocking=False):
        log(f"收到{zh}訊號，但上一個動作還在執行，略過")
        return
    try:
        wait = COOLDOWN - (time.time() - last_done)
        if wait > 0:
            log(f"收到{zh}訊號，冷卻中（還剩 {wait:.0f} 秒），略過")
            return
        if action == "out" and scaled():
            log("收到擴展訊號，但 app-3、app-4 已經在線上，略過")
            return
        if action == "in" and not scaled():
            log("收到縮減訊號，但目前沒有擴展節點，略過")
            return

        script, start_msg, done_msg = {
            "out": ("scale_out.py", "🚀 排隊過多，開始自動擴展 app-3、app-4（約 2～3 分鐘）",
                    "✅ 自動擴展完成：app-3、app-4 已加入負載平衡"),
            "in": ("scale_in.py", "📉 流量已降低，開始自動縮減 app-3、app-4",
                   "✅ 自動縮減完成：app-3、app-4 已移出並刪除"),
        }[action]
        log(start_msg)
        discord(start_msg)
        t0 = time.time()
        r = subprocess.run([sys.executable, str(HERE / script)], cwd=HERE)
        if r.returncode == 0:
            msg = f"{done_msg}（耗時 {time.time() - t0:.0f} 秒）"
        else:
            msg = f"⚠️ {script} 執行失敗（代碼 {r.returncode}），請看 Windows 視窗的訊息"
        log(msg)
        discord(msg)
        last_done = time.time()
    finally:
        lock.release()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        state = "已擴展（4 台）" if scaled() else "未擴展（2 台）"
        busy = "執行中" if lock.locked() else "待命"
        self._reply(200, f"HA2 autoscale：{state}，{busy}\n")

    def do_POST(self):
        if self.client_address[0] not in ALLOW:
            return self._reply(403, "forbidden\n")
        try:
            body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
        except ValueError:
            return self._reply(400, "bad json\n")
        for a in body.get("alerts", []):
            name = a.get("labels", {}).get("alertname")
            if a.get("status") == "firing" and name in ACTIONS:
                log(f"收到告警 {name}")
                threading.Thread(target=run, args=(ACTIONS[name],), daemon=True).start()
                break
        self._reply(200, "ok\n")   # 立刻回覆，Alertmanager 不用等 VM 建立完成

    def _reply(self, code, text):
        data = text.encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):   # 不印每一筆 HTTP 紀錄
        pass


def main():
    if not os.environ.get("HA2_GUEST_PASS"):
        # scale_out.py 是子程式，無法在背景詢問密碼，所以先問一次再傳下去
        os.environ["HA2_GUEST_PASS"] = getpass.getpass("範本機 root 密碼：")
    log(f"自動擴展服務啟動，監聽 0.0.0.0:{PORT}（Ctrl + C 結束）")
    log("目前狀態：" + ("已擴展" if scaled() else "未擴展"))
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("結束")
