from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser

BASE = Path(__file__).resolve().parent
os.chdir(BASE)
BASE_URL = "http://127.0.0.1:8030"
URL = BASE_URL + "/?v=11-7-goal-perfect"
REQ = BASE / "requirements.txt"


def banner():
    print("=" * 60)
    print("   UNIBOT FINANCE MODERN V11.7 - FINAL/CLEAN")
    print("   HỆ THỐNG CHATBOT AI QUẢN LÝ TÀI CHÍNH CÁ NHÂN & TIẾT KIỆM")
    print("   Sinh viên thực hiện: Phạm Như Ý - MSV: 2375620225 - Lớp CNTTA K11")
    print("   Giảng viên hướng dẫn: PGS.TS. Ngô Tứ Thành")
    print("=" * 60)
    print(f"Địa chỉ truy cập: {URL}")
    print()


def ensure_packages():
    required = {
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
        "sqlalchemy": "sqlalchemy",
        "pydantic_settings": "pydantic_settings",
        "numpy": "numpy",
        "httpx": "httpx",
    }
    missing = [name for name, module in required.items() if importlib.util.find_spec(module) is None]
    if not missing:
        print("Thư viện Python: OK")
        return
    print("Thiếu thư viện:", ", ".join(missing))
    print("Đang cài đặt tự động từ requirements.txt ...")
    if not REQ.exists():
        raise RuntimeError("Không tìm thấy requirements.txt")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQ)])


def wait_and_open():
    health = BASE_URL + "/health"
    for _ in range(120):
        try:
            with urllib.request.urlopen(health, timeout=1) as r:
                if r.status == 200:
                    print("Backend UniBOT Finance: OK - Đang mở trình duyệt...")
                    webbrowser.open(URL, new=2)
                    return
        except Exception:
            time.sleep(0.5)
    print("Không tự mở được trình duyệt. Hãy mở thủ công:", URL)


def main():
    banner()
    try:
        ensure_packages()
        import app.main  # noqa: F401
        print("V11.7 Backend import: OK")
        threading.Thread(target=wait_and_open, daemon=True).start()
        import uvicorn
        uvicorn.run("app.main:app", host="127.0.0.1", port=8030, log_level="info")
    except KeyboardInterrupt:
        print("\nĐã dừng UniBOT Finance.")
    except Exception as exc:
        print("\nCÓ LỖI KHI KHỞI ĐỘNG:")
        print(type(exc).__name__ + ":", exc)
        print("\nHãy kiểm tra lại cài đặt hoặc báo lại giảng viên.")
        try:
            input("Nhấn Enter để đóng...")
        except EOFError:
            pass
        raise


if __name__ == "__main__":
    main()
