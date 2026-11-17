# HA2：自動化高可用網站與監控系統

在一台 Windows 電腦上，用 VMware Workstation 與 Rocky Linux 10.2 建置的高可用網站實驗環境。使用者只連一個虛擬 IP；負載平衡器或網站主機故障時自動接手，網站更新與增減主機的過程中服務不中斷。

| 功能 | 實作 |
|---|---|
| 固定入口 | Keepalived VRRP，VIP 192.168.20.50 |
| 負載平衡 | HAProxy roundrobin、第 7 層健康檢查、maxconn 排隊 |
| 容錯接手 | 檢查腳本降低 priority，VIP 自動轉移（實測中斷約 5.5 秒） |
| 自動建機 | Python 呼叫 vmrun，從範本快照複製並設定主機身分 |
| 自動部署 | Ansible playbook，冪等可重跑 |
| 滾動更新 | HAProxy Runtime API 先 drain 再更新，使用者零失敗 |
| 擴展縮減 | 一鍵 linked clone 加入、drain 後關機刪除；排隊過多自動擴展、流量降低自動縮減 |
| 監控 | Prometheus、Grafana、HAProxy 內建指標、即時監控頁 |
| 告警 | Prometheus 告警規則 → Alertmanager → Discord（發生與恢復都通知） |

## 架構

```
                    使用者（瀏覽器）
                          │
                 VIP 192.168.20.50
                ┌─────────┴─────────┐
          lb-a（主）.31  ◀─VRRP─▶  lb-b（備）.32
          HAProxy + Keepalived      HAProxy + Keepalived
                └─────────┬─────────┘
        ┌─────────┬───────┴───┬──────────┐
     app-1 .41  app-2 .42  app-3 .43  app-4 .44
      Nginx      Nginx     （擴展）   （擴展）

  ctl 192.168.20.5：Ansible、Prometheus、Alertmanager、Grafana、NAT 閘道
  Windows：clone_vms.py、scale_out.py、scale_in.py
  網段：VMnet2 host-only 192.168.20.0/24
```

## 目錄

```
ha2-lab/
├── README.md
├── docs/
│   └── COMMANDS.md          從零建置的逐步指令手冊（每步附正確結果）
├── ansible/                 在 ctl 上執行
│   ├── ansible.cfg
│   ├── inventory.ini
│   ├── group_vars/all.yml   版本號、VRRP 密碼、監控軟體版本
│   ├── group_vars/monitor/secret.yml.example  Discord Webhook 範例（複製成 secret.yml，不上傳）
│   ├── apps.yml             網站（Nginx、監控頁）
│   ├── balancers.yml        HAProxy + Keepalived
│   ├── rolling.yml          滾動更新
│   ├── scale_out.yml        擴展（由 scale_out.py 呼叫）
│   ├── scale_in.yml         縮減（由 scale_in.py 呼叫）
│   ├── monitoring.yml       node_exporter + Prometheus
│   ├── alerting.yml         Alertmanager（送 Discord）
│   ├── grafana.yml          Grafana
│   ├── site_tasks.yml       apps 與 rolling 共用的網站內容任務
│   ├── files/index.html     即時監控頁（含目前告警）
│   ├── files/alert_rules.yml 6 條告警規則
│   └── templates/           haproxy、keepalived、prometheus、nginx 等設定模板
└── windows/                 在 Windows 上執行
    ├── clone_vms.py         自動複製 lb-a、lb-b、app-1、app-2
    ├── scale_out.py         一鍵擴展 app-3、app-4
    ├── scale_in.py          一鍵縮減
    └── autoscale.py         接收 Alertmanager 告警，自動執行擴展／縮減
```

## 快速開始

完整步驟請看 **[docs/COMMANDS.md](docs/COMMANDS.md)**。主要流程：

1. 手動建立 ctl（兩張網卡，兼 NAT 閘道）與範本機 app-tpl，拍快照 `tpl-base`
2. ctl 上 `git clone` 本專案
3. Windows 執行 `python clone_vms.py` 建立 4 台主機
4. ctl 上依序執行：

```bash
cd ~/ha2-lab/ansible
ansible-playbook apps.yml --limit '!scale'
ansible-playbook balancers.yml
ansible-playbook monitoring.yml --limit '!scale'
cp group_vars/monitor/secret.yml.example group_vars/monitor/secret.yml   # 填入 Discord Webhook
ansible-playbook alerting.yml
ansible-playbook grafana.yml
```

5. 瀏覽器開 http://192.168.20.50

## 常用操作

| 操作 | 指令 |
|---|---|
| 滾動更新到 v2 | `ansible-playbook rolling.yml -e site_version=v2`（在 ctl） |
| 擴展 | `python scale_out.py`（在 Windows） |
| 縮減 | `python scale_in.py`（在 Windows） |

## 注意事項

- 這是實驗環境：使用 root 密碼登入、明文 VRRP 密碼、只有 HTTP，**請勿直接用於正式環境**。
- `windows/clone_vms.py` 不存放密碼，執行時從環境變數 `HA2_GUEST_PASS` 讀取或詢問。
- 擴展用的 linked clone 依賴 app-tpl 與快照 tpl-base，兩者都不能刪除。

## 軟體版本

Rocky Linux 10.2 ‧ VMware Workstation 17 ‧ HAProxy 3.0 ‧ Keepalived ‧ Nginx 1.26 ‧ ansible-core 2.16 ‧ Prometheus 3.14 ‧ node_exporter 1.12 ‧ Grafana

## 告警規則

| 告警 | 條件 | 等級 |
|---|---|---|
| HAProxyDown | LB 的 HAProxy 指標抓不到超過 10 秒 | critical |
| VIPOnBackup | 流量出現在備援 lb-b（代表 VIP 已轉移） | warning |
| AppServerDown | HAProxy 健康檢查判定網站主機 DOWN | critical |
| InstanceDown | 主機的 node_exporter 抓不到超過 30 秒 | critical |
| BackendQueueHigh | 後端排隊超過 5 個連線達 15 秒 → **自動擴展** | warning |
| BackendIdle | 擴展節點在線且每秒請求數低於 30 達 1 分鐘 → **自動縮減**（不發 Discord） | info |
| HighCPU | CPU 使用率超過 80% 達 1 分鐘 | warning |

> Discord Webhook 網址放在 `ansible/group_vars/monitor/secret.yml`，已列入 `.gitignore`。

## 自動擴展流程

```
Prometheus 規則 BackendQueueHigh / BackendIdle
        │ 告警
        ▼
Alertmanager（ctl :9093） ──▶ Discord 通知
        │ webhook
        ▼
autoscale.py（Windows :9095，只接受 ctl）
        │ 防重複：執行中略過、冷卻 180 秒、已擴展就不再擴展
        ▼
scale_out.py / scale_in.py ──▶ vmrun + ssh ctl 執行 Ansible
```

## 互動版指令手冊

`docs/commands.html` 是指令手冊的網頁版：每個指令都有「複製」按鈕，每個小步驟可以勾選完成並顯示進度，還能搜尋、切換 Ansible 資料夾路徑。用瀏覽器直接打開即可。

修改 `docs/COMMANDS.md` 後重新產生：

```bash
pip install markdown
python tools/build_commands_html.py
```
