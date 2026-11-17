"""一鍵擴展：以 linked clone 建立 app-3、app-4，再由 ctl 的 Ansible 部署並加入負載平衡。

使用方式：
    python scale_out.py          # 建立 app-3、app-4
    python scale_out.py app-3    # 只建立 app-3
需求：與 clone_vms.py 放在同一個資料夾；Windows 已設定免密碼 SSH 到 ctl。
"""
import subprocess
import sys
from clone_vms import BASE, clone, vmrun

CTL = "root@192.168.20.5"
NODES = {"app-3": "192.168.20.43", "app-4": "192.168.20.44"}


def main():
    names = sys.argv[1:] or list(NODES)
    for n in names:
        if n not in NODES:
            raise SystemExit(f"不認識的節點：{n}，可用：{', '.join(NODES)}")
        vmx = BASE / n / f"{n}.vmx"
        if vmx.exists():
            print(f"[{n}] 已存在，確認已開機")
            if str(vmx).lower() not in vmrun("list").lower():
                vmrun("start", vmx, "nogui")
        else:
            clone(n, NODES[n], "linked", 1)

    limit = ",".join(names)
    print(f"部署並加入負載平衡：{limit}")
    subprocess.run(["ssh", CTL, f"cd ~/ha2-lab/ansible && ansible-playbook scale_out.yml --limit {limit}"], check=True)
    print("擴展完成")


if __name__ == "__main__":
    main()
