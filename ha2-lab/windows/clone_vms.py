"""從範本快照 tpl-base 完整複製 lb-a、lb-b、app-1、app-2，並逐台設定主機身分。

使用方式（Windows cmd）：
    cd /d C:\\VM
    python clone_vms.py

root 密碼：先設定環境變數 HA2_GUEST_PASS，沒有設定時執行會詢問（不會顯示在畫面）。
"""
import getpass
import os
import re
import subprocess
import time
from pathlib import Path

# VMware Workstation 17 預設路徑；舊版可能在 Program Files (x86)
VMRUN_CANDIDATES = [
    r"C:\Program Files\VMware\VMware Workstation\vmrun.exe",
    r"C:\Program Files (x86)\VMware\VMware Workstation\vmrun.exe",
]
BASE = Path(r"C:\VM")                     # 所有 VM 所在的資料夾
TPL = BASE / "app-tpl" / "app-tpl.vmx"    # 範本機
SNAP = "tpl-base"                         # 範本快照名稱
GUEST_USER = "root"

# 主機名稱: (IP, vCPU)
HOSTS = {
    "lb-a":  ("192.168.20.31", 2),
    "lb-b":  ("192.168.20.32", 2),
    "app-1": ("192.168.20.41", 1),
    "app-2": ("192.168.20.42", 1),
}

_guest_pass = None


def find_vmrun():
    for p in VMRUN_CANDIDATES:
        if Path(p).exists():
            return p
    raise SystemExit("找不到 vmrun.exe，請用 where /r C:\\ vmrun.exe 查詢後修改 VMRUN_CANDIDATES")


VMRUN = find_vmrun()


def guest_pass():
    global _guest_pass
    if _guest_pass is None:
        _guest_pass = os.environ.get("HA2_GUEST_PASS") or getpass.getpass("範本機 root 密碼：")
    return _guest_pass


def vmrun(*args, guest=False):
    cmd = [VMRUN, "-T", "ws"]
    if guest:
        cmd += ["-gu", GUEST_USER, "-gp", guest_pass()]
    cmd += [str(a) for a in args]
    print("  vmrun", args[0])
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{args[0]} 失敗：{r.stdout}{r.stderr}")
    return r.stdout


def set_vcpu(vmx: Path, n: int):
    text = vmx.read_text(encoding="utf-8")
    if re.search(r'^numvcpus\s*=', text, re.M):
        text = re.sub(r'^numvcpus\s*=.*$', f'numvcpus = "{n}"', text, flags=re.M)
    else:
        text += f'\nnumvcpus = "{n}"\n'
    vmx.write_text(text, encoding="utf-8")


def wait_tools(vmx: Path, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        if "running" in vmrun("checkToolsState", vmx):
            return
        time.sleep(5)
    raise TimeoutError(f"{vmx.name} 的 VMware Tools 沒有啟動")


def set_identity(vmx: Path, name: str, ip: str):
    """開機後透過 VMware Tools 修改主機名稱、IP，並重新產生 machine-id 與 SSH 主機金鑰。"""
    script = f"""
hostnamectl set-hostname {name}
nmcli con mod ens160 ipv4.addresses {ip}/24
rm -f /etc/machine-id && systemd-machine-id-setup
rm -f /etc/ssh/ssh_host_*
"""
    vmrun("runScriptInGuest", vmx, "/bin/bash", script, guest=True)


def clone(name: str, ip: str, mode: str = "full", vcpu: int = 1):
    vmx = BASE / name / f"{name}.vmx"
    if vmx.exists():
        print(f"[{name}] 已存在，跳過")
        return vmx
    print(f"[{name}] {mode} clone 中")
    vmx.parent.mkdir(parents=True, exist_ok=True)
    vmrun("clone", TPL, vmx, mode, f"-snapshot={SNAP}", f"-cloneName={name}")
    set_vcpu(vmx, vcpu)

    print(f"[{name}] 開機並修改設定")
    vmrun("start", vmx, "nogui")
    wait_tools(vmx)
    set_identity(vmx, name, ip)

    print(f"[{name}] 重新開機套用設定")
    vmrun("stop", vmx, "soft")
    vmrun("start", vmx, "nogui")
    print(f"[{name}] 完成 → {ip}")
    return vmx


def main():
    if str(TPL).lower() in vmrun("list").lower():
        raise SystemExit("app-tpl 還開著，請先關機")
    for name, (ip, vcpu) in HOSTS.items():
        clone(name, ip, "full", vcpu)
    print("全部完成")


if __name__ == "__main__":
    main()
