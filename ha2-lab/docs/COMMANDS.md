# 指令手冊：從零建置 HA2 高可用網站與監控系統

這份手冊把整個專題拆成 **16 個步驟（0～15）、85 個小步驟**。每個小步驟都寫了：

- **在哪裡執行**：Windows、VMware 畫面、ctl、或某台主機
- **指令**：可以直接複製貼上
- **✅ 正確結果**：看到這個才進下一步
- **❌ 不一樣時**：最常見的原因與處理方式（只有容易出錯的步驟才有）

設計原理與測試數據請看技術文件；這份只放「怎麼做」與「做對了長什麼樣子」。

---

## 目錄

| 步驟 | 內容 | 執行位置 |
|---|---|---|
| [0](#步驟-0vmware-網路準備) | VMware 網路準備 | Windows |
| [1](#步驟-1建立-ctl) | 建立 ctl | VMware、ctl |
| [2](#步驟-2把-ctl-設定成-nat-閘道) | 把 ctl 設定成 NAT 閘道 | ctl |
| [3](#步驟-3ctl-的事前準備) | ctl 的事前準備 | Windows、ctl |
| [4](#步驟-4建立範本機-app-tpl) | 建立範本機 app-tpl | VMware、app-tpl、ctl |
| [5](#步驟-5更新範本並拍快照) | 更新範本並拍快照 | ctl、VMware |
| [6](#步驟-6用-python-自動複製-4-台主機) | 用 Python 自動複製 4 台主機 | Windows、ctl |
| [7](#步驟-7確認-ansible-連線) | 確認 Ansible 連線 | ctl |
| [8](#步驟-8部署網站-appsyml) | 部署網站 | ctl |
| [9](#步驟-9部署負載平衡-balancersyml) | 部署負載平衡 | ctl、瀏覽器 |
| [10](#步驟-10故障切換測試) | 故障切換測試 | ctl、Windows |
| [11](#步驟-11監控與告警prometheus--grafana--alertmanager) | 監控與告警（Discord） | ctl、瀏覽器 |
| [12](#步驟-12壓力測試) | 壓力測試 | ctl、瀏覽器 |
| [13](#步驟-13滾動更新) | 滾動更新 | ctl、瀏覽器 |
| [14](#步驟-14擴展與縮減) | 擴展與縮減（手動、自動） | Windows、瀏覽器 |
| [15](#步驟-15收尾) | 收尾 | VMware |
| [附錄](#附錄-a常見問題) | 常見問題、速查 | — |

---

## 開始之前

### 需要的環境

| 項目 | 需求 |
|---|---|
| 電腦 | Windows 10/11，記憶體 16 GB 以上，硬碟可用 100 GB 以上 |
| 虛擬化 | VMware Workstation Pro 17 |
| 作業系統映像 | Rocky Linux 10.2 DVD ISO |
| Python | Windows 上的 Python 3（安裝時勾選 Add python.exe to PATH） |
| SSH 工具 | Windows 內建 ssh，或 MobaXterm |

### 主機與 IP 一覽

| 主機 | IP | vCPU / RAM | 角色 |
|---|---|---|---|
| Windows（VMnet2 介面） | 192.168.20.1 | – | 瀏覽器、執行 Python |
| ctl | 192.168.20.5（ens224）＋ NAT 網卡（ens160） | 2 / 6 GB | Ansible、Prometheus、Grafana、NAT 閘道 |
| VIP | 192.168.20.50 | – | 網站唯一入口 |
| lb-a | 192.168.20.31 | 2 / 1 GB | HAProxy + Keepalived（MASTER） |
| lb-b | 192.168.20.32 | 2 / 1 GB | HAProxy + Keepalived（BACKUP） |
| app-1、app-2 | 192.168.20.41、.42 | 1 / 2 GB | Nginx 網站 |
| app-3、app-4 | 192.168.20.43、.44 | linked clone | 擴展節點，平時不存在 |
| app-tpl | 192.168.20.49 | 1 / 2 GB | 範本機，快照 tpl-base |

### 提示字元對照

| 看到 | 代表在 |
|---|---|
| `C:\>` | Windows 的 cmd |
| `[root@ctl ~]#` | ctl（建議從 Windows 用 SSH 連進去，才能複製貼上） |
| `[root@ctl ansible]#` | ctl 的 `~/ha2-lab/ansible` 資料夾，**所有 ansible 指令都要在這裡執行** |
| `[root@app-tpl ~]#` | app-tpl 的 VMware 畫面 |

---

## 步驟 0：VMware 網路準備

### 0-1 關閉不需要的 VM

**在哪裡執行：** VMware

如果電腦上有其他實驗用的 VM，先全部 Shut Down Guest，節省記憶體。

**✅ 正確結果：** VMware 左側清單的 VM 都顯示 Powered Off。

### 0-2 確認網段沒有人在用

**在哪裡執行：** Windows cmd

```
ipconfig
```

**✅ 正確結果：** 所有介面都**沒有** `192.168.20.x` 的位址。

**❌ 不一樣時：** 如果實體網路或其他 VMnet 已經用了 192.168.20.x，Windows 會不知道封包該走哪張網卡。請整份手冊換成別的網段（例如 192.168.30.x）。

### 0-3 新增 VMnet2

**在哪裡執行：** VMware → Edit → Virtual Network Editor

1. 右下角按 **Change Settings**（需要系統管理員權限）
2. **Add Network...** → 選 **VMnet2** → OK
3. 選中 VMnet2，下方設定：

| 項目 | 設定 |
|---|---|
| 類型 | **Host-only** |
| Connect a host virtual adapter to this network | ✅ 勾選 |
| Use local DHCP service | ⬜ **不勾** |
| Subnet IP | `192.168.20.0` |
| Subnet mask | `255.255.255.0` |

4. **Apply** → OK

### 0-4 確認 Windows 拿到 VMnet2 的位址

**在哪裡執行：** Windows cmd

```
ipconfig
```

**✅ 正確結果：**

```
乙太網路卡 VMware Network Adapter VMnet2:
   IPv4 位址 . . . . . . . . . . . . : 192.168.20.1
   子網路遮罩 . . . . . . . . . . . . : 255.255.255.0
```

### 0-5 建立 VM 資料夾

**在哪裡執行：** 檔案總管

建立 `C:\VM`，之後所有 VM 都放這裡。

**✅ 正確結果：** `C:\VM` 資料夾存在。

> 放在其他位置也可以，但第 6 步要把 `clone_vms.py` 的 `BASE` 改成同一個路徑。

---

## 步驟 1：建立 ctl

### 1-1 新增 VM

**在哪裡執行：** VMware → File → New Virtual Machine → **Typical**

| 畫面 | 設定 |
|---|---|
| Guest OS installation | I will install the operating system later |
| Guest OS | Linux → Red Hat Enterprise Linux 10（沒有就選 9）64-bit |
| 名稱 / 位置 | `ctl` / `C:\VM\ctl` |
| 硬碟 | 40 GB，Store as a single file |

按 **Customize Hardware**：

| 項目 | 設定 |
|---|---|
| Memory | 6144 MB |
| Processors | 2 |
| New CD/DVD | Use ISO image → Rocky Linux 10.2 ISO |
| Network Adapter | **NAT** |
| Add → Network Adapter | 第二張，**Custom → VMnet2** |
| Sound Card、Printer | Remove |

**✅ 正確結果：** 硬體清單有兩張 Network Adapter：一張 NAT、一張 Custom (VMnet2)。

### 1-2 安裝 Rocky Linux 10.2

**在哪裡執行：** ctl 的 VMware 畫面

| 項目 | 設定 |
|---|---|
| 語言 | English |
| Installation Destination | 選硬碟 → Automatic |
| Network & Host Name | 第一張網卡切 **ON**；Host Name 填 `ctl` 後按 **Apply** |
| Software Selection | **Minimal Install** |
| Root Password | 設定密碼，勾選 **Allow root SSH login with password** |
| Time & Date | Asia/Taipei |

Begin Installation → 完成後 Reboot。

**✅ 正確結果：** 開機後出現 `localhost login:` 或 `ctl login:`，可以用 root 登入。

### 1-3 確認網卡名稱

**在哪裡執行：** ctl 的 VMware 畫面

```bash
ip -br a
```

**✅ 正確結果：**

```
lo        UNKNOWN   127.0.0.1/8 ::1/128
ens160    UP        192.168.80.x/24 ...
ens224    UP        ...
```

- `ens160` 是 NAT 網卡，有 192.168.80.x（VMware NAT 網段，數字依電腦而定）
- 第二張網卡**通常叫 `ens224`**，這份手冊以 ens224 為準

**❌ 不一樣時：** 如果第二張網卡不是 ens224（例如 ens192），之後所有寫 `ens224` 的地方都換成你看到的名稱。

### 1-4 設定主機名稱與時區

**在哪裡執行：** ctl 的 VMware 畫面

```bash
hostnamectl set-hostname ctl
timedatectl set-timezone Asia/Taipei
hostnamectl --static
timedatectl | grep "Time zone"
```

**✅ 正確結果：**

```
ctl
                Time zone: Asia/Taipei (CST, +0800)
```

> 時區一定要設，否則之後終端機時間和 Grafana 時間會對不起來。

### 1-5 設定第二張網卡（ens224）

**在哪裡執行：** ctl 的 VMware 畫面

先看連線名稱：

```bash
nmcli con show
```

**情況 A：NAME 欄有 `ens224`**

```bash
nmcli con mod ens224 ipv4.method manual ipv4.addresses 192.168.20.5/24 ipv4.gateway "" ipv4.never-default yes connection.autoconnect yes
nmcli con up ens224
```

**情況 B：沒有 `ens224` 這個連線**

```bash
nmcli con add type ethernet ifname ens224 con-name ens224 ipv4.method manual ipv4.addresses 192.168.20.5/24 ipv4.never-default yes connection.autoconnect yes
nmcli con up ens224
```

檢查：

```bash
ip -br a show ens224
ip route
```

**✅ 正確結果：**

```
ens224    UP    192.168.20.5/24 ...
default via 192.168.80.2 dev ens160 proto dhcp ...
192.168.20.0/24 dev ens224 proto kernel scope link src 192.168.20.5 ...
192.168.80.0/24 dev ens160 proto kernel scope link src 192.168.80.x ...
```

重點：`default` 開頭的路由**只有一行**，而且走 `ens160`。

**❌ 不一樣時：** 出現兩行 `default`，代表 ens224 也有閘道，再執行一次情況 A 的指令（`ipv4.gateway ""` 和 `ipv4.never-default yes`）。

---

## 步驟 2：把 ctl 設定成 NAT 閘道

### 2-1 兩張網卡分到不同的防火牆區域

**在哪裡執行：** ctl

```bash
nmcli con mod ens160 connection.zone external
nmcli con mod ens224 connection.zone internal
nmcli con up ens160
nmcli con up ens224
firewall-cmd --get-active-zones
```

**✅ 正確結果：**

```
external
  interfaces: ens160
internal
  interfaces: ens224
public (default)
```

`public (default)` 底下沒有網卡是正常的，它只是預設區域。

### 2-2 允許內部往外轉送

**在哪裡執行：** ctl

```bash
firewall-cmd --permanent --new-policy int2ext
firewall-cmd --permanent --policy int2ext --add-ingress-zone internal
firewall-cmd --permanent --policy int2ext --add-egress-zone external
firewall-cmd --permanent --policy int2ext --set-target ACCEPT
firewall-cmd --reload
```

**✅ 正確結果：** 每一行都回應 `success`。

### 2-3 驗證閘道設定

**在哪裡執行：** ctl

```bash
firewall-cmd --zone=external --query-masquerade
sysctl net.ipv4.ip_forward
ping -c 3 8.8.8.8
```

**✅ 正確結果：**

```
yes
net.ipv4.ip_forward = 1
64 bytes from 8.8.8.8: icmp_seq=1 ttl=128 time=11.3 ms
...
3 packets transmitted, 3 received, 0% packet loss
```

記下這裡的 **ttl=128**，第 4 步會用來比較。

---

## 步驟 3：ctl 的事前準備

### 3-1 從 Windows 用 SSH 連進 ctl

**在哪裡執行：** Windows cmd

```
ssh root@192.168.20.5
```

第一次會問 `Are you sure you want to continue connecting (yes/no)?`，輸入 `yes`，再輸入 ctl 的 root 密碼（輸入時畫面不會顯示）。

**✅ 正確結果：** 出現 `[root@ctl ~]#`。

> 之後所有「在 ctl 執行」的步驟都在這個視窗操作。cmd 視窗裡**按滑鼠右鍵就是貼上**。一次只貼一段，不要把兩段指令黏在一起貼。

### 3-2 寫入主機名稱對照表

**在哪裡執行：** ctl

```bash
cat >> /etc/hosts <<'EOF'
192.168.20.5   ctl
192.168.20.31  lb-a
192.168.20.32  lb-b
192.168.20.41  app-1
192.168.20.42  app-2
192.168.20.43  app-3
192.168.20.44  app-4
192.168.20.49  app-tpl
EOF
tail -8 /etc/hosts
```

**✅ 正確結果：** 最後 8 行就是上面的 8 筆紀錄，**沒有重複**。

**❌ 不一樣時：** 不小心貼了兩次，用 `vi /etc/hosts` 刪掉重複的行（游標移到該行按 `dd`，最後輸入 `:wq` 存檔）。

### 3-3 產生 SSH 金鑰

**在哪裡執行：** ctl

```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519
```

**✅ 正確結果：** 出現一個方框圖案，上方有一行結尾是 `root@ctl`。

### 3-4 安裝 git、Ansible 與壓力測試工具

**在哪裡執行：** ctl

```bash
dnf install -y git ansible-core httpd-tools
ansible-galaxy collection install ansible.posix 'community.general:>=10,<11'
ansible --version | head -1
ansible-galaxy collection list | grep -E "ansible.posix|community.general"
```

**✅ 正確結果：**

```
ansible [core 2.16.x]
ansible.posix      x.x.x
community.general  10.x.x
```

> 指定 community.general 10 版，是因為更新的版本不支援 ansible-core 2.16，會一直出現警告。

### 3-5 下載專題程式碼

**在哪裡執行：** ctl

```bash
git clone https://github.com/agc277/ha2-lab.git ~/ha2-lab
ls ~/ha2-lab/ansible
```

**✅ 正確結果：**

```
ansible.cfg  apps.yml  balancers.yml  files  grafana.yml  group_vars  inventory.ini
monitoring.yml  rolling.yml  scale_in.yml  scale_out.yml  site_tasks.yml  templates
```

---

## 步驟 4：建立範本機 app-tpl

### 4-1 新增 VM

**在哪裡執行：** VMware → File → New Virtual Machine → Typical

| 項目 | 設定 |
|---|---|
| 名稱 / 位置 | `app-tpl` / `C:\VM\app-tpl` |
| 硬碟 | 20 GB，Store as a single file |
| Memory / Processors | 2048 MB / 1 |
| CD/DVD | Rocky Linux 10.2 ISO |
| Network Adapter | **Custom → VMnet2**（只有這一張） |
| Sound Card、Printer | Remove |

**✅ 正確結果：** 只有一張 Network Adapter，顯示 Custom (VMnet2)。

### 4-2 安裝 Rocky Linux 10.2

**在哪裡執行：** app-tpl 的 VMware 畫面

| 項目 | 設定 |
|---|---|
| Host Name | `app-tpl` → **Apply** |
| ens160 | Configure → IPv4 Settings → Method **Manual**，Address `192.168.20.49`、Netmask `24`、Gateway **`192.168.20.5`**、DNS `8.8.8.8` → **Save**，外面開關切 **ON** |
| Software Selection | Minimal Install |
| Root Password | 設定並**記下來**（第 6 步的 Python 會用到），勾選 Allow root SSH login with password |
| Time & Date | Asia/Taipei |

Gateway 填的是 ctl，因為 VMnet2 沒有 VMware 幫忙上網。

**✅ 正確結果：** 安裝完成，重開機後能用 root 登入。

### 4-3 檢查並補上網路設定

**在哪裡執行：** app-tpl 的 VMware 畫面（這台還沒網路，只能直接打字）

```bash
hostname
ip -br a show ens160
```

**✅ 正確結果：** `app-tpl`，以及 `ens160 UP 192.168.20.49/24`。

**❌ 不一樣時（安裝畫面的設定沒套用到）：**

```bash
hostnamectl set-hostname app-tpl
timedatectl set-timezone Asia/Taipei
nmcli con show
```

NAME 欄有 `ens160`：

```bash
nmcli con mod ens160 ipv4.method manual ipv4.addresses 192.168.20.49/24 ipv4.gateway 192.168.20.5 ipv4.dns 8.8.8.8 connection.autoconnect yes
nmcli con up ens160
```

NAME 欄沒有 `ens160`：

```bash
nmcli con add type ethernet ifname ens160 con-name ens160 ipv4.method manual ipv4.addresses 192.168.20.49/24 ipv4.gateway 192.168.20.5 ipv4.dns 8.8.8.8 connection.autoconnect yes
nmcli con up ens160
```

### 4-4 確認範本機能經過 ctl 上網

**在哪裡執行：** app-tpl 的 VMware 畫面

```bash
ip route
ping -c 3 192.168.20.5
ping -c 3 google.com
rpm -q open-vm-tools python3
```

**✅ 正確結果：**

```
default via 192.168.20.5 dev ens160 proto static metric 100
192.168.20.0/24 dev ens160 proto kernel scope link src 192.168.20.49 metric 100
64 bytes from 192.168.20.5: icmp_seq=1 ttl=64 ...
64 bytes from ... (142.250.x.x): icmp_seq=1 ttl=127 ...
open-vm-tools-13.x.x-x.el10.x86_64
python3-3.12.x-x.el10_x.x86_64
```

ping google 的 **ttl=127**，比 ctl 的 128 少 1，代表封包經過 ctl 轉送，**閘道成功**。

**❌ 不一樣時：**

| 現象 | 原因 |
|---|---|
| `Network is unreachable` | 網路沒設定到，回到 4-3 |
| ping ctl 通、ping google 不通 | ctl 的轉送有問題，回到步驟 2 檢查 zone 與 policy |
| ping 8.8.8.8 通、ping google.com 不通 | DNS 沒設定，檢查 `ipv4.dns` |

### 4-5 把 ctl 的金鑰放進 app-tpl

**在哪裡執行：** ctl

```bash
ssh-copy-id root@app-tpl
ssh app-tpl hostname
```

第一次會問 yes/no，輸入 `yes`，再輸入 app-tpl 的 root 密碼。

**✅ 正確結果：** 第二行**不用輸入密碼**就顯示 `app-tpl`。

> 這把金鑰會被之後所有 clone 出來的主機繼承，所以 ctl 可以免密碼登入每一台。

---

## 步驟 5：更新範本並拍快照

### 5-1 更新系統

**在哪裡執行：** ctl

```bash
ssh app-tpl "dnf -y update && dnf clean all"
```

**✅ 正確結果：** 最後出現 `Complete!`（沒有可更新的套件時會顯示 `Nothing to do.`，也算正常）。

### 5-2 關機

**在哪裡執行：** ctl

```bash
ssh app-tpl poweroff
```

**✅ 正確結果：** VMware 裡 app-tpl 變成 Powered Off（ssh 連線被中斷的訊息是正常的）。

### 5-3 拍快照

**在哪裡執行：** VMware → 選 app-tpl → VM → Snapshot → Take Snapshot

| 欄位 | 內容 |
|---|---|
| Name | `tpl-base` |
| Description | Rocky 10.2 + 網路 + ctl 金鑰 |

**✅ 正確結果：** VM → Snapshot → Snapshot Manager 看得到 **tpl-base**。

> 名稱要完全一樣，Python 腳本用這個名稱找快照。

---

## 步驟 6：用 Python 自動複製 4 台主機

### 6-1 確認 Python

**在哪裡執行：** Windows cmd

```
python --version
```

**✅ 正確結果：** `Python 3.x.x`

**❌ 不一樣時：** 出現「找不到」或跳出 Microsoft Store，到 python.org 下載安裝，安裝時勾選 **Add python.exe to PATH**，再重開 cmd。

### 6-2 確認 vmrun 的位置

**在哪裡執行：** Windows cmd

```
where /r "C:\Program Files" vmrun.exe
```

**✅ 正確結果：**

```
C:\Program Files\VMware\VMware Workstation\vmrun.exe
```

腳本會自動檢查這個路徑和 `Program Files (x86)` 底下的路徑。

**❌ 不一樣時：** 執行 `where /r C:\ vmrun.exe` 找出實際位置，把它加進 `clone_vms.py` 開頭的 `VMRUN_CANDIDATES`。

### 6-3 取得腳本

**在哪裡執行：** 瀏覽器、檔案總管

1. 到 GitHub repo 頁面 → **Code → Download ZIP**
2. 解壓縮，把 `windows` 資料夾裡的 3 個檔案複製到 `C:\VM`：
   - `clone_vms.py`
   - `scale_out.py`
   - `scale_in.py`

確認：

```
cd /d C:\VM
dir *.py
findstr /c:"BASE =" clone_vms.py
```

**✅ 正確結果：**

```
clone_vms.py  scale_in.py  scale_out.py
BASE = Path(r"C:\VM")                     # 所有 VM 所在的資料夾
```

**❌ 不一樣時：** VM 放在別的資料夾，就用記事本把 `BASE` 改成那個路徑。**存檔時編碼選 UTF-8**，否則 Python 會出現 `SyntaxError: Non-UTF-8 code`。

### 6-4 設定範本機密碼

**在哪裡執行：** Windows cmd（同一個視窗）

```
set HA2_GUEST_PASS=你的app-tpl密碼
```

**✅ 正確結果：** 沒有任何輸出。這個設定只在目前這個 cmd 視窗有效，密碼不會寫進檔案。

> 不設定也可以，執行腳本時會詢問密碼。

### 6-5 執行複製

**在哪裡執行：** Windows cmd（同一個視窗）

```
python clone_vms.py
```

**✅ 正確結果：**（每台約 1～3 分鐘）

```
  vmrun list
[lb-a] full clone 中
  vmrun clone
[lb-a] 開機並修改設定
  vmrun start
  vmrun checkToolsState
  vmrun runScriptInGuest
[lb-a] 重新開機套用設定
  vmrun stop
  vmrun start
[lb-a] 完成 → 192.168.20.31
...
[app-2] 完成 → 192.168.20.42
全部完成
```

**❌ 不一樣時：**

| 錯誤訊息 | 原因與處理 |
|---|---|
| `app-tpl 還開著，請先關機` | 回到 5-2 |
| `找不到 vmrun.exe` | 回到 6-2 |
| `clone 失敗 ... snapshot` | 快照名稱不是 tpl-base，回到 5-3 |
| `runScriptInGuest 失敗` | root 密碼錯誤，重新執行 6-4 |
| 某一台做到一半失敗 | 在 VMware 把那台關機、刪除 `C:\VM\那台名稱` 資料夾，再重跑；已完成的會自動跳過 |

### 6-6 把 4 台加到 VMware 清單

**在哪裡執行：** VMware → File → Open

依序打開：

- `C:\VM\lb-a\lb-a.vmx`
- `C:\VM\lb-b\lb-b.vmx`
- `C:\VM\app-1\app-1.vmx`
- `C:\VM\app-2\app-2.vmx`

**✅ 正確結果：** 左側清單出現 4 台，都是 Powered On。

### 6-7 驗證 4 台的身分

**在哪裡執行：** ctl

```bash
for h in lb-a lb-b app-1 app-2; do
  echo "===== $h ====="
  ssh -o StrictHostKeyChecking=accept-new $h "hostname; ip -br a show ens160; nproc; cat /etc/machine-id"
done
```

**✅ 正確結果：** 4 台都**不用輸入密碼**，而且：

| 主機 | IP | nproc |
|---|---|---|
| lb-a | 192.168.20.31 | 2 |
| lb-b | 192.168.20.32 | 2 |
| app-1 | 192.168.20.41 | 1 |
| app-2 | 192.168.20.42 | 1 |

最後一行的 machine-id，**4 台都不一樣**。

### 6-8 確認 4 台都能上網

**在哪裡執行：** ctl

```bash
for h in lb-a lb-b app-1 app-2; do ssh $h "ping -c 1 -W 2 google.com >/dev/null && echo $h 上網OK"; done
```

**✅ 正確結果：**

```
lb-a 上網OK
lb-b 上網OK
app-1 上網OK
app-2 上網OK
```

---

## 步驟 7：確認 Ansible 連線

> 從這一步開始，**所有 ansible 指令都要先 `cd ~/ha2-lab/ansible`**，提示字元要是 `[root@ctl ansible]#`。Ansible 會讀目前資料夾的 `ansible.cfg` 和 `inventory.ini`，不在這個資料夾會出現 `Could not match supplied host pattern`。
>
> 另外，app-3、app-4 平時不存在，手動執行時加上 `--limit '!scale'`（排除 scale 群組），避免出現 unreachable。

### 7-1 測試所有主機

**在哪裡執行：** ctl

```bash
cd ~/ha2-lab/ansible
ansible all -m ping --limit '!scale'
```

**✅ 正確結果：** ctl、lb-a、lb-b、app-1、app-2 共 5 台都是綠色：

```
lb-a | SUCCESS => {
    ...
    "ping": "pong"
}
```

### 7-2 統一所有主機的時區

**在哪裡執行：** ctl

```bash
ansible all --limit '!scale' -m community.general.timezone -a "name=Asia/Taipei"
ansible all --limit '!scale' -a "date"
```

**✅ 正確結果：** 第二行 5 台都顯示 `CST`（台灣時間）。

### 7-3 練習用群組指定主機

**在哪裡執行：** ctl

```bash
ansible balancers -a "hostname"
ansible apps -a "nproc"
```

**✅ 正確結果：**

```
lb-a | CHANGED | rc=0 >>
lb-a
lb-b | CHANGED | rc=0 >>
lb-b
app-1 | CHANGED | rc=0 >>
1
app-2 | CHANGED | rc=0 >>
1
```

用 `-a` 執行指令一律顯示黃色 CHANGED，是正常的。

---

## 步驟 8：部署網站（apps.yml）

### 8-1 檢查語法

**在哪裡執行：** ctl（`~/ha2-lab/ansible`）

```bash
ansible-playbook apps.yml --syntax-check
```

**✅ 正確結果：** `playbook: apps.yml`

### 8-2 部署

**在哪裡執行：** ctl

```bash
ansible-playbook apps.yml --limit '!scale'
```

**✅ 正確結果：** 最後的 PLAY RECAP：

```
app-1   : ok=12  changed=9  unreachable=0  failed=0 ...
app-2   : ok=12  changed=9  unreachable=0  failed=0 ...
```

數字可能略有不同，重點是 **failed=0**。

### 8-3 確認網站正常

**在哪裡執行：** ctl

```bash
curl -s app-1/whoami.json
curl -s app-2/whoami.json
curl app-1/health
```

**✅ 正確結果：**

```
{"host": "app-1", "version": "v1"}
{"host": "app-2", "version": "v1"}
OK
```

> 用瀏覽器開 `http://192.168.20.41` 會看到監控頁，但下方顯示「無法取得監控數據」，因為 Prometheus 第 11 步才裝，這是正常的。

### 8-4 再執行一次（確認冪等性）

**在哪裡執行：** ctl

```bash
ansible-playbook apps.yml --limit '!scale'
```

**✅ 正確結果：** PLAY RECAP 兩台都是 **changed=0**。同一個 playbook 重跑不會重複修改，這就是冪等性。

---

## 步驟 9：部署負載平衡（balancers.yml）

### 9-1 部署

**在哪裡執行：** ctl（`~/ha2-lab/ansible`）

```bash
ansible-playbook balancers.yml --syntax-check
ansible-playbook balancers.yml
```

**✅ 正確結果：**

```
lb-a   : ok=10  changed=9  unreachable=0  failed=0 ...
lb-b   : ok=10  changed=9  unreachable=0  failed=0 ...
```

**❌ 不一樣時：** 出現 `No module named 'semanage'`，代表安裝清單少了 `python3-libsemanage`，檢查 balancers.yml 的「安裝套件」。

### 9-2 確認 VIP 在 lb-a 上

**在哪裡執行：** ctl

```bash
ansible balancers -a "ip -br a show ens160"
```

**✅ 正確結果：**

```
lb-a | CHANGED | rc=0 >>
ens160   UP   192.168.20.31/24 192.168.20.50/24 ...
lb-b | CHANGED | rc=0 >>
ens160   UP   192.168.20.32/24 ...
```

lb-a 多一個 **192.168.20.50/24**，lb-b 沒有。

### 9-3 確認輪流分配

**在哪裡執行：** ctl

```bash
for i in 1 2 3 4; do curl -s -i 192.168.20.50/whoami.json | grep -iE "x-lb-node|host"; echo ---; done
```

**✅ 正確結果：**

```
x-lb-node: lb-a
{"host": "app-1", "version": "v1"}
---
x-lb-node: lb-a
{"host": "app-2", "version": "v1"}
---
...
```

`x-lb-node` 每次都是 lb-a，`host` 在 app-1、app-2 之間輪流。

> 標頭名稱是小寫，因為 HAProxy 3.x 會把標頭轉成小寫，所以 grep 要加 `-i`。

### 9-4 查看 HAProxy 狀態頁

**在哪裡執行：** Windows 瀏覽器

```
http://192.168.20.31:8405/stats
```

**✅ 正確結果：**

| 伺服器 | 顏色 | LastChk |
|---|---|---|
| app-1、app-2 | 綠色 UP | L7OK/200 |
| app-3、app-4 | 紅色 DOWN | L4TOUT（主機不存在，正常） |

### 9-5 確認管理 socket 可以使用

**在哪裡執行：** ctl

```bash
ssh lb-a "echo 'show servers state apps' | socat stdio /var/lib/haproxy/stats" | head -3
```

**✅ 正確結果：** 第一行是版本號（例如 `1`），接著是 `# be_id be_name srv_id ...` 開頭的欄位名稱和資料。滾動更新和擴展會透過這個 socket 移出、加回主機。

---

## 步驟 10：故障切換測試

需要 **3 個視窗**：

| 視窗 | 用途 |
|---|---|
| A | ctl，抓封包 |
| B | ctl，下指令 |
| C | Windows cmd，持續 ping VIP |

### 10-1 開始持續 ping

**在哪裡執行：** 視窗 C（Windows cmd）

```
ping -t 192.168.20.50
```

**✅ 正確結果：** 持續出現 `回覆自 192.168.20.50: 位元組=32 時間<1ms TTL=64`。讓它一直跑，測試全部結束後按 Ctrl+C。

### 10-2 記下目前 VIP 的 MAC

**在哪裡執行：** 另開一個 Windows cmd

```
arp -a | findstr 192.168.20.50
```

**✅ 正確結果：** `192.168.20.50  00-0c-29-xx-xx-xx  動態`，這個 MAC 是 lb-a 的網卡。把它記下來。

### 10-3 抓 VRRP 心跳與 ARP

**在哪裡執行：** 視窗 A（ctl）

```bash
ssh lb-b "timeout 30 tcpdump -l -i ens160 -nn 'vrrp or (arp and host 192.168.20.50)'"
```

**✅ 正確結果：** 每秒出現一行：

```
IP 192.168.20.31 > 192.168.20.32: VRRPv2, Advertisement, vrid 61, prio 120, authtype simple, intvl 1s, length 20
```

> `-l` 讓輸出即時顯示；沒有加的話，經過 ssh 執行時要等結束才會一次印出。

### 10-4 停止 lb-a 的 HAProxy

**在哪裡執行：** 視窗 B（ctl），在視窗 A 開始出現心跳後執行

```bash
ssh lb-a systemctl stop haproxy
```

**✅ 正確結果（視窗 A）：**

```
IP 192.168.20.31 > 192.168.20.32: VRRPv2, ..., prio 120, ...    ← 正常
IP 192.168.20.31 > 192.168.20.32: VRRPv2, ..., prio 90, ...     ← 檢查失敗，120 − 30
IP 192.168.20.32 > 192.168.20.31: VRRPv2, ..., prio 100, ...    ← lb-b 成為 MASTER
ARP, Request who-has 192.168.20.50 tell 192.168.20.50, ...      ← Gratuitous ARP
```

截圖保存，這是報告的證據。

### 10-5 確認 VIP 已經轉移

**在哪裡執行：** 視窗 B（ctl）

```bash
ansible balancers -a "ip -br a show ens160"
curl -s -i 192.168.20.50/whoami.json | grep -iE "x-lb-node|host"
```

**✅ 正確結果：**

- `192.168.20.50/24` 出現在 **lb-b**
- `x-lb-node: lb-b`，網站照常回應

再到 Windows 執行 `arp -a | findstr 192.168.20.50`：**同一個 IP，MAC 變成 lb-b 的**。

### 10-6 恢復 lb-a

**在哪裡執行：** 視窗 B（ctl）

```bash
ssh lb-a systemctl start haproxy
sleep 8
ansible balancers -a "ip -br a show ens160"
```

**✅ 正確結果：** VIP 回到 **lb-a**。lb-a 的 priority 恢復 120，比 lb-b 高，會把 VIP 搶回來（preempt）。

### 10-7 量測實際中斷時間

**在哪裡執行：** 視窗 A（ctl）

```bash
while true; do
  printf "%s " "$(date +%T.%N | cut -c1-12)"
  curl -s -o /dev/null -m 1 -w "%{http_code}\n" 192.168.20.50/
  sleep 0.2
done
```

畫面開始一直出現 `時間 200` 後，在**視窗 B** 執行：

```bash
ssh lb-a systemctl stop haproxy
```

**✅ 正確結果（視窗 A）：**

```
23:01:37.627 200
23:01:37.839 000     ← 開始失敗
...
23:01:43.278 000     ← 最後一次失敗
23:01:43.487 200     ← 恢復，已切到 lb-b
```

第一個 `000` 到恢復 `200` 之間約 **4～6 秒**。按 Ctrl+C 停止迴圈，再恢復 lb-a：

```bash
ssh lb-a systemctl start haproxy
```

> 不要用 `ab -r` 的失敗數來判斷中斷：被拒絕的連線會瞬間重試，失敗數會被放大到幾十萬。

### 10-8 整台 LB 當機

**在哪裡執行：** 視窗 B（ctl）

```bash
ssh lb-a poweroff
sleep 6
curl -s -i 192.168.20.50/whoami.json | grep -iE "x-lb-node|host"
```

**✅ 正確結果：** `x-lb-node: lb-b`，網站照常回應。

接著在 VMware 把 lb-a 開機，約 1 分鐘後：

```bash
ansible balancers -a "ip -br a show ens160"
```

**✅ 正確結果：** VIP 回到 lb-a。

### 10-9 網站主機故障

**在哪裡執行：** 視窗 B（ctl）

```bash
ssh app-1 systemctl stop nginx
sleep 8
for i in 1 2 3 4; do curl -s 192.168.20.50/whoami.json; echo; done
```

**✅ 正確結果：** 4 次都是 `"host": "app-2"`；狀態頁 app-1 變紅色 DOWN。

恢復：

```bash
ssh app-1 systemctl start nginx
```

**✅ 正確結果：** 約 4 秒後狀態頁 app-1 變回綠色。

### 10-10 復原檢查

**在哪裡執行：** ctl（`~/ha2-lab/ansible`）

```bash
ansible balancers -m shell -a "systemctl is-active haproxy keepalived; ip -br a show ens160"
ansible apps -a "systemctl is-active nginx"
```

**✅ 正確結果：** 全部 `active`，VIP 在 **lb-a**。回到視窗 C 按 Ctrl+C，看 ping 遺失幾個封包。

---

## 步驟 11：監控與告警（Prometheus + Grafana + Alertmanager）

### 11-1 安裝 node_exporter 與 Prometheus

**在哪裡執行：** ctl（`~/ha2-lab/ansible`）

```bash
ansible-playbook monitoring.yml --syntax-check
ansible-playbook monitoring.yml --limit '!scale'
```

**✅ 正確結果：** ctl、lb-a、lb-b、app-1、app-2 全部 **failed=0**。

**❌ 不一樣時：** 下載那一步出現 404，代表版本號不對。到 https://prometheus.io/download/ 查最新版，修改 `group_vars/all.yml` 再執行。

### 11-2 確認數據有在收集

**在哪裡執行：** ctl

```bash
curl -s app-1:9100/metrics | grep -m1 "^node_cpu"
curl -s localhost:9090/-/healthy
curl -s 192.168.20.31:8405/metrics | grep -m1 "^haproxy_frontend"
```

**✅ 正確結果：**

```
node_cpu_guest_seconds_total{cpu="0",mode="nice"} 0
Prometheus Server is Healthy.
haproxy_frontend_status{proxy="web_in"} 1
```

（第一、三行的指標名稱可能不同，有 `node_` 與 `haproxy_frontend` 開頭的資料就對了）

### 11-3 查看 Prometheus 目標

**在哪裡執行：** Windows 瀏覽器

```
http://192.168.20.5:9090/targets
```

**✅ 正確結果：**

| 群組 | 狀態 |
|---|---|
| node | **5 / 7 up**：ctl、lb-a、lb-b、app-1、app-2 為 UP；app-3、app-4 為 DOWN（不存在，正常） |
| haproxy | **2 / 2 up** |

### 11-4 安裝 Grafana

**在哪裡執行：** ctl

```bash
ansible-playbook grafana.yml
systemctl is-active grafana-server
```

**✅ 正確結果：** ctl **failed=0**，第二行顯示 `active`。

### 11-5 登入 Grafana 並匯入儀表板

**在哪裡執行：** Windows 瀏覽器

1. 開 `http://192.168.20.5:3000`，帳號密碼 `admin / admin`，登入後設定新密碼
2. 左側 **Connections → Data sources**，確認已經有 **Prometheus**
3. 左側 **Dashboards → New → Import**，輸入 ID → Load → 資料來源選 Prometheus → Import：

| ID | 儀表板 |
|---|---|
| 1860 | Node Exporter Full |
| 12693 | HAProxy 2 Full |

**✅ 正確結果：** Node Exporter Full 選 lb-a 能看到 CPU、記憶體、網路圖表；HAProxy 2 Full 有請求數圖表。

### 11-6 建立「VIP 所在位置」面板

**在哪裡執行：** Grafana → Dashboards → New → New dashboard → Add visualization → Prometheus

查詢切到 **Code**，輸入：

```
sum by (host) (rate(haproxy_frontend_http_requests_total{proxy="web_in"}[15s]))
```

| 設定 | 值 |
|---|---|
| Options → Legend | `{{host}}` |
| 標題 | 各 LB 每秒請求數（VIP 所在位置） |
| 右上時間範圍 | Last 5 minutes |
| 自動更新 | 5s |

按 **Save**。

**✅ 正確結果：** 圖例顯示 lb-a、lb-b 兩條線。重做一次 10-4、10-6，可以看到流量 lb-a → lb-b → lb-a。

### 11-7 確認監控頁

**在哪裡執行：** ctl，再到 Windows 瀏覽器

```bash
curl -s "192.168.20.50/api/query?query=site_version_info" | head -c 200; echo
```

**✅ 正確結果：** 開頭是 `{"status":"success","data":{...` 並包含 app-1、app-2 的版本。

瀏覽器開 `http://192.168.20.50`，按 **Ctrl + F5**：

- 上方顯示「目前負載平衡器 lb-a」
- 最近請求分配出現 app-1、app-2 交替
- lb-a 卡片有藍框與「持有 VIP」，app 卡片顯示「服務中」與版本號

### 11-8 建立 Discord Webhook

**在哪裡執行：** Discord（電腦版或網頁版）

1. 建立一個自己的伺服器（或用現有的），新增文字頻道 `#ha2-alerts`
2. 頻道右邊齒輪 **編輯頻道 → 整合 → Webhook → 新 Webhook**
3. 名稱改成 `HA2 Alert` → **複製 Webhook 網址**

**✅ 正確結果：** 剪貼簿裡有一串 `https://discord.com/api/webhooks/數字/英數字` 的網址。

> 這串網址等於「發訊息到你頻道的鑰匙」，**不要貼到 GitHub、投影片或截圖裡**。

### 11-9 把 Webhook 寫進 secret.yml

**在哪裡執行：** ctl（`~/ha2-lab/ansible`）

```bash
cp group_vars/monitor/secret.yml.example group_vars/monitor/secret.yml
vi group_vars/monitor/secret.yml      # 把網址換成 11-8 複製的
chmod 600 group_vars/monitor/secret.yml
ansible ctl -m debug -a "msg={{ discord_webhook_url[:35] }}"
git status --short
```

**✅ 正確結果：** debug 顯示 `"msg": "https://discord.com/api/webhooks/"`；`git status` **看不到 secret.yml**（已被 .gitignore 排除）。

**❌ 不一樣時：** 顯示 `discord_webhook_url is undefined` → 檔案路徑要是 `group_vars/monitor/secret.yml`，而且 ctl 要在 inventory 的 `[monitor]` 群組裡。

### 11-10 載入告警規則、安裝 Alertmanager

**在哪裡執行：** ctl（`~/ha2-lab/ansible`）

```bash
ansible-playbook monitoring.yml --limit '!scale'
ansible-playbook alerting.yml
ansible-playbook apps.yml --limit '!scale'      # 更新監控頁（多了告警區）
systemctl is-active prometheus alertmanager
curl -s localhost:9093/-/healthy; echo
```

**✅ 正確結果：** 三個 playbook 都 **failed=0**；接著兩行 `active`；最後 `OK`。

**❌ 不一樣時：**

| 現象 | 處理 |
|---|---|
| 「放入告警規則」失敗 | promtool 檢查沒過，看錯誤訊息裡的行號修正 `files/alert_rules.yml` |
| 「確認已設定 Discord Webhook」失敗 | 回到 11-9 |
| 下載 alertmanager 404 | 到 https://prometheus.io/download/#alertmanager 查版本，改 `group_vars/all.yml` 的 `alertmanager_version` |

### 11-11 確認規則與 Alertmanager 連上

**在哪裡執行：** Windows 瀏覽器

```
http://192.168.20.5:9090/alerts
http://192.168.20.5:9090/status        （往下找 Alertmanagers）
http://192.168.20.5:9093
```

**✅ 正確結果：**

- `/alerts` 有 **ha2** 群組 6 條規則：HAProxyDown、VIPOnBackup、AppServerDown、InstanceDown、BackendQueueHigh、HighCPU，全部綠色 **Inactive**
- Alertmanagers 顯示 `http://localhost:9093/api/v2/alerts`
- 9093 網頁打得開，Alerts 頁目前是空的

### 11-12 告警演示 1：LB 故障

**在哪裡執行：** 先在 Windows 開監控頁 `http://192.168.20.50`（它每秒查詢一次，剛好提供流量），再到 ctl

```bash
ssh lb-a "systemctl stop haproxy"
```

等約 30 秒。

**✅ 正確結果：**

| 位置 | 看到 |
|---|---|
| Prometheus `/alerts` | HAProxyDown、VIPOnBackup 由黃色 Pending 變紅色 **Firing** |
| Discord | `🔴 告警：HAProxyDown`（lb-a 的 HAProxy 停止回應）與 `🔴 告警：VIPOnBackup`（VIP 已切到備援 lb-b） |
| 監控頁 | 「目前告警」出現紅色標籤，事件紀錄寫「告警發生」 |

復原：

```bash
ssh lb-a "systemctl start haproxy"
```

**✅ 正確結果：** 約 30～60 秒後 Discord 收到兩則 `🟢 已恢復`，監控頁告警區回到「目前沒有告警」。

**❌ 不一樣時：** 只有 Pending 沒有 Firing → 停的時間不到 `for` 設定的 10 秒；Firing 但 Discord 沒訊息 → `journalctl -u alertmanager -n 20` 看錯誤，多半是 webhook 網址貼錯。

### 11-13 告警演示 2：網站主機故障、排隊過長

**在哪裡執行：** ctl（`~/ha2-lab/ansible`）

```bash
ssh app-1 "systemctl stop nginx"
```

**✅ 正確結果：** 約 20～30 秒後 Discord 收到 `🔴 告警：AppServerDown`（app-1 健康檢查失敗）；網站仍可正常瀏覽（只剩 app-2 回應）。

恢復 app-1：

```bash
ssh app-1 "systemctl start nginx"
```

**✅ 正確結果：** 稍後收到 `🟢 已恢復：AppServerDown`。

排隊告警（需要 12-1 的測試檔）：

```bash
ab -n 200000 -c 50 http://192.168.20.50/bench.txt
```

**✅ 正確結果：** 測試進行中收到 `🔴 告警：BackendQueueHigh`，測試結束後收到 `🟢 已恢復`。

> 這則告警在 14-5 之後會變成自動擴展的觸發訊號；在那之前只會通知。

---

## 步驟 12：壓力測試

### 12-1 建立測試檔

**在哪裡執行：** ctl（`~/ha2-lab/ansible`）

```bash
ansible-playbook apps.yml --limit '!scale'
curl -s -o /dev/null -w "%{http_code} %{size_download} bytes\n" 192.168.20.50/bench.txt
```

**✅ 正確結果：** `200 101316 bytes`（大小約 10 萬 bytes 即可）

> 測試檔由 `apps.yml` 建立（約 10 萬 bytes），擴展出來的 app-3、app-4 也會自動有。一定要先確認是 **200**：如果是 404，ab 會把它算成「完成」或 Non-2xx，數據會完全錯誤。

### 12-2 測試 1：基準效能

**在哪裡執行：** ctl

```bash
ab -n 2000 -c 10 http://192.168.20.50/bench.txt
```

**✅ 正確結果：**

```
Document Length:        101316 bytes
Complete requests:      2000
Failed requests:        0
Requests per second:    約 800～900 [#/sec]
```

並且**沒有** `Non-2xx responses` 這一行。

### 12-3 測試 2：超過 maxconn，觀察排隊

**在哪裡執行：** 先開瀏覽器 `http://192.168.20.31:8405/stats`，再到 ctl 執行

```bash
ab -n 5000 -c 50 http://192.168.20.50/bench.txt
```

**✅ 正確結果：**

- ab：`Failed requests: 0`；每秒請求數和測試 1 差不多，平均回應時間變長
- 狀態頁（測試進行中重新整理）：app-1、app-2 的 Sessions Cur 頂在 **8**，Backend 的 Queue 出現數字

### 12-4 測試 3：持續 60 秒，VIP 是否穩定

**在哪裡執行：** 視窗 B 先執行（監看 Keepalived 狀態變化）

```bash
ssh lb-a "journalctl -u keepalived -f -n 0"
```

視窗 A 執行：

```bash
ab -t 60 -n 1000000 -c 20 http://192.168.20.50/bench.txt
```

**✅ 正確結果：**

- ab：`Failed requests: 0`
- 視窗 B：60 秒內**沒有任何輸出**（沒有出現 `Entering BACKUP STATE`）
- Grafana Node Exporter Full 選 lb-a（時間範圍 Last 15 minutes）：網路流量達數百 Mb/s，CPU 明顯上升

視窗 B 按 Ctrl+C 結束。

---

## 步驟 13：滾動更新

### 13-1 準備觀察畫面

**在哪裡執行：** 瀏覽器開監控頁 `http://192.168.20.50` 與狀態頁 `http://192.168.20.31:8405/stats`；ctl 視窗 A 執行

```bash
while true; do
  printf "%s " "$(date +%T)"
  curl -s -m 1 192.168.20.50/whoami.json | grep -oE "app-[0-9]|v[0-9]+" | paste -sd' '
  sleep 0.3
done
```

**✅ 正確結果：** 持續出現 `12:30:01 app-1 v1`、`12:30:01 app-2 v1` 交替。

### 13-2 執行滾動更新

**在哪裡執行：** ctl 視窗 B（`~/ha2-lab/ansible`）

```bash
ansible-playbook rolling.yml -e site_version=v2
```

**✅ 正確結果：**

| 階段 | 視窗 A | 狀態頁 | 監控頁事件紀錄 |
|---|---|---|---|
| app-1 更新中 | 全部 `app-2 v1` | app-1 咖啡色 MAINT | app-1 狀態：服務中 → 維護中 |
| app-1 加回 | `app-1 v2`、`app-2 v1` 交替 | app-1 綠色 | app-1 版本更新 v1 → v2 |
| app-2 更新中 | 全部 `app-1 v2` | app-2 MAINT | app-2 狀態：服務中 → 維護中 |
| 完成 | `app-1 v2`、`app-2 v2` 交替 | 全部綠色 | app-2 版本更新 v1 → v2 |

PLAY RECAP 兩台 **failed=0**；視窗 A **沒有空白行**。

### 13-3 把新版本寫進設定

**在哪裡執行：** ctl

```bash
sed -i 's/^site_version: .*/site_version: v2/' group_vars/all.yml
grep site_version group_vars/all.yml
```

**✅ 正確結果：** `site_version: v2`

> 這樣之後擴展出來的主機也會是 v2，不會和線上版本不一致。

---

## 步驟 14：擴展與縮減

### 14-1 設定 Windows 免密碼 SSH 到 ctl

**在哪裡執行：** Windows cmd（**一次只貼一行**）

```
ssh-keygen -t ed25519
```

三個問題都直接按 Enter。

```
type %USERPROFILE%\.ssh\id_ed25519.pub | ssh root@192.168.20.5 "cat >> ~/.ssh/authorized_keys"
```

輸入 ctl 密碼（最後一次）。

```
ssh root@192.168.20.5 hostname
```

**✅ 正確結果：** 最後一行**不用密碼**就顯示 `ctl`。

### 14-2 擴展：建立 app-3、app-4

**在哪裡執行：** 瀏覽器開著監控頁與狀態頁；Windows cmd

```
cd /d C:\VM
set HA2_GUEST_PASS=你的app-tpl密碼
python scale_out.py
```

**✅ 正確結果：**

```
[app-3] linked clone 中
...
[app-3] 完成 → 192.168.20.43
[app-4] linked clone 中
...
[app-4] 完成 → 192.168.20.44
部署並加入負載平衡：app-3,app-4
...
PLAY RECAP
app-3   : ok=..  changed=..  unreachable=0  failed=0
app-4   : ok=..  changed=..  unreachable=0  failed=0
擴展完成
```

- 狀態頁：app-3、app-4 從紅色變**綠色 UP**
- 監控頁：出現 app-3、app-4 卡片，事件紀錄寫入「節點加入」
- 最近請求分配：app-1～app-4 四台輪流

### 14-3 縮減：移除 app-3、app-4

**在哪裡執行：** Windows cmd

```
python scale_in.py
```

**✅ 正確結果：**

```
移出負載平衡並關機：app-3,app-4
...
TASK [從兩台 LB 移出（等處理中的請求完成）]
changed: [app-3 -> lb-a(192.168.20.31)] => (item=lb-a)
...
TASK [關機]
...
[app-3] 已刪除
[app-4] 已刪除
縮減完成
```

- 狀態頁：app-3、app-4 先變咖啡色 MAINT
- 監控頁：卡片消失，事件紀錄寫入「節點移除」
- 請求分配回到 app-1、app-2

> 縮減後狀態頁的 app-3、app-4 停在 MAINT 是正常的；下次擴展時 scale_out.yml 會重新啟用。

### 14-4 開放 Windows 防火牆給 Alertmanager

**在哪裡執行：** Windows PowerShell（**以系統管理員身分執行**）

```powershell
New-NetFirewallRule -DisplayName "HA2 autoscale" -Direction Inbound -Protocol TCP -LocalPort 9095 -RemoteAddress 192.168.20.5 -Action Allow -Profile Any
```

**✅ 正確結果：** 顯示 `DisplayName : HA2 autoscale`、`Enabled : True`。

> 只允許 ctl（192.168.20.5）連進來，其他電腦連不到這個 port。

### 14-5 啟動自動擴展服務

**在哪裡執行：** Windows cmd（`autoscale.py` 與 `scale_out.py`、`clone_vms.py` 放在同一個資料夾）

```
set HA2_GUEST_PASS=範本機的root密碼
set HA2_DISCORD_WEBHOOK=貼上11-8的Webhook網址
python autoscale.py
```

**✅ 正確結果：**

```
16:30:01 自動擴展服務啟動，監聽 0.0.0.0:9095（Ctrl + C 結束）
16:30:01 目前狀態：未擴展
```

這個視窗**保持開著**，接下來的動作都會印在這裡。

**❌ 不一樣時：** `OSError: [WinError 10048]` → 9095 已被占用（可能已經開了一個），關掉另一個視窗。

### 14-6 讓 Alertmanager 連上自動擴展服務

**在哪裡執行：** ctl（`~/ha2-lab/ansible`）

```bash
ansible-playbook monitoring.yml --limit '!scale'
ansible-playbook alerting.yml
ansible-playbook apps.yml --limit '!scale'
curl -s 192.168.20.1:9095/
```

**✅ 正確結果：** playbook 都是 **failed=0**；最後一行 `HA2 autoscale：未擴展（2 台），待命`。Prometheus `/alerts` 多了 **BackendIdle**，共 7 條規則。

**❌ 不一樣時：** curl 卡住或 `No route to host` → 回到 14-4 檢查防火牆規則；`Connection refused` → 14-5 的視窗沒有在執行。

### 14-7 自動擴展與自動縮減演示

**在哪裡執行：** Windows 瀏覽器開監控頁 `http://192.168.20.50`，再到 ctl

```bash
ab -t 300 -n 10000000 -c 50 http://192.168.20.50/bench.txt
```

（持續 5 分鐘的壓力，讓擴展有時間完成）

**✅ 正確結果（依時間順序）：**

| 約略時間 | 看到 |
|---|---|
| 0:20 | Discord `🔴 告警：BackendQueueHigh`；監控頁出現「排隊過多，自動擴展」 |
| 0:20 | Discord `🚀 排隊過多，開始自動擴展`；Windows 視窗開始 clone |
| 2:30～3:30 | Discord `✅ 自動擴展完成`；監控頁出現 app-3、app-4 卡片，請求分配到 4 台 |
| 5:00 | ab 結束 |
| 6:10 左右 | 監控頁出現「流量低，自動縮減」；Discord `📉 流量已降低，開始自動縮減` |
| 7:00 左右 | Discord `✅ 自動縮減完成`；app-3、app-4 卡片消失 |

ab 的結果 **Failed requests: 0**、沒有 `Non-2xx responses`——擴展和縮減過程中沒有請求失敗。

**❌ 不一樣時：**

| 現象 | 原因與處理 |
|---|---|
| 有 BackendQueueHigh 但沒開始擴展 | Windows 視窗沒收到 → 14-6 的 curl 測試 |
| Windows 視窗出現「冷卻中，略過」 | 上次動作完成未滿 3 分鐘，Alertmanager 2 分鐘後會再送一次 |
| 擴展完成後很快又被縮減 | ab 已結束；正常行為，縮減條件是每秒請求數低於 30 持續 1 分鐘 |
| ab 出現大量 `Non-2xx responses`、`Length` 失敗 | app-3、app-4 沒有 bench.txt 而回 404；確認 `apps.yml` 有「壓力測試檔 bench.txt」這個任務，在 ctl 執行 `ansible scale -m stat -a path=/usr/share/nginx/html/bench.txt` 檢查 |
| 一直沒有縮減 | 監控頁或其他流量超過每秒 30 個請求，可到 Prometheus 查 `sum(rate(haproxy_backend_http_requests_total{proxy="apps"}[1m]))` |

---

## 步驟 15：收尾

### 15-1 每台拍快照

**在哪裡執行：** VMware

ctl、lb-a、lb-b、app-1、app-2 各拍一個快照，名稱 `final`。

**✅ 正確結果：** 每台的 Snapshot Manager 都有 final。

> **不要刪除 app-tpl 和它的 tpl-base 快照**，擴展用的 linked clone 依賴它們。

### 15-2 最終檢查

**在哪裡執行：** ctl（`~/ha2-lab/ansible`）

```bash
ansible all --limit '!scale' -m ping
ansible balancers -a "ip -br a show ens160"
curl -s -o /dev/null -w "%{http_code}\n" 192.168.20.50/
```

**✅ 正確結果：** 5 台 pong、VIP 在 lb-a、最後一行 `200`。

---

## 附錄 A：常見問題

| 現象 | 原因 | 處理 |
|---|---|---|
| 第二張網卡找不到 ens192 | VMware 依 PCI 插槽命名，實際是 ens224 | `ip -br a` 確認名稱 |
| 安裝後 hostname、IP 沒生效 | 安裝畫面沒按 Apply、Save，或網卡沒切 ON | 4-3 用指令補設定 |
| `Network is unreachable` | 網卡沒有 IP 或閘道 | 4-3 |
| Python `SyntaxError: Non-UTF-8 code` | 記事本存成 ANSI（Big5） | 另存新檔，編碼選 UTF-8 |
| Python `FileNotFoundError: [WinError 2]` | 找不到 vmrun.exe | 6-2 |
| `Could not match supplied host pattern` | 不在 `~/ha2-lab/ansible` | `cd ~/ha2-lab/ansible` |
| `No module named 'semanage'` | 受控端缺 python3-libsemanage | 加入安裝清單 |
| community.general does not support Ansible version | collection 版本太新 | 3-4 指定 10 版 |
| grep 不到 X-LB-Node | HAProxy 3.x 標頭轉小寫 | `grep -i` |
| 經 ssh 跑 tcpdump 沒輸出 | 輸出被緩衝 | 加 `-l` |
| ab 結果 `Non-2xx responses` | 測試檔不存在，全部 404 | 12-1 先確認 200 |
| ab -r 失敗數幾十萬 | 被拒絕的連線瞬間重試 | 改用 10-7 的 curl 迴圈 |
| 監控頁「無法取得監控數據」 | Prometheus 還沒裝，或 SELinux 擋住 Nginx 轉送 | 完成步驟 11；確認 apps.yml 的 httpd_can_network_connect |
| Grafana 圖表時間差 13 小時 | 主機時區錯誤 | 7-2 |
| 執行 apps.yml 出現 app-3、app-4 unreachable | 擴展節點不存在 | 加 `--limit '!scale'` |
| 告警 Firing 但 Discord 沒收到 | Webhook 網址錯誤或 ctl 連不到外網 | `journalctl -u alertmanager -n 20`；11-9 |

## 附錄 B：常用檢查指令速查

| 想知道 | 指令（在 ctl 的 `~/ha2-lab/ansible`） |
|---|---|
| VIP 在哪台 | `ansible balancers -a "ip -br a show ens160"` |
| 誰在回應網站 | `curl -s -i 192.168.20.50/whoami.json \| grep -iE "x-lb-node\|host"` |
| 所有服務狀態 | `ansible balancers -m shell -a "systemctl is-active haproxy keepalived"` |
| Keepalived 紀錄 | `ssh lb-a "journalctl -u keepalived -n 20"` |
| HAProxy 設定是否正確 | `ssh lb-a "haproxy -c -f /etc/haproxy/haproxy.cfg"` |
| HAProxy 後端狀態 | `ssh lb-a "echo 'show servers state apps' \| socat stdio /var/lib/haproxy/stats"` |
| Prometheus 目標 | 瀏覽器 `http://192.168.20.5:9090/targets` |
| 目前有哪些告警 | `curl -s localhost:9093/api/v2/alerts \| grep -o '"alertname":"[A-Za-z]*"'` |

## 附錄 C：網址一覽

| 用途 | 網址 |
|---|---|
| 監控頁（網站） | http://192.168.20.50 |
| HAProxy 狀態頁 | http://192.168.20.31:8405/stats、http://192.168.20.32:8405/stats |
| Prometheus | http://192.168.20.5:9090 |
| Grafana | http://192.168.20.5:3000 |
| Prometheus 告警規則 | http://192.168.20.5:9090/alerts |
| Alertmanager | http://192.168.20.5:9093 |
| 自動擴展服務狀態 | http://192.168.20.1:9095 （在 Windows 上） |
