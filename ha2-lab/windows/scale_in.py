"""一鍵縮減：先在兩台 LB 上 drain，再關機並刪除 app-3、app-4。

使用方式：
    python scale_in.py           # 縮減 app-3、app-4
    python scale_in.py app-4     # 只縮減 app-4
"""
import subprocess
import sys
import time
from clone_vms import BASE, vmrun

CTL = "root@192.168.20.5"


def main():
    names = sys.argv[1:] or ["app-3", "app-4"]
    limit = ",".join(names)
    print(f"移出負載平衡並關機：{limit}")
    subprocess.run(["ssh", CTL, f"cd ~/ha2-lab/ansible && ansible-playbook scale_in.yml --limit {limit}"], check=True)

    for n in names:
        vmx = BASE / n / f"{n}.vmx"
        if not vmx.exists():
            continue
        for _ in range(30):
            if str(vmx).lower() not in vmrun("list").lower():
                break
            time.sleep(3)
        else:
            vmrun("stop", vmx, "hard")
        vmrun("deleteVM", vmx)
        print(f"[{n}] 已刪除")
    print("縮減完成")


if __name__ == "__main__":
    main()
