# 관리자용 라이선스 발급 도구 (빌드 제외 — 관리자만 사용)
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import time
import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import datetime, timedelta

# ── license_manager.py 와 동일한 시크릿 ────────────────────────────────
_JWT_SECRET = "cb4155372cbeeeee804e32e03a29e73a8a6d9576720689dcbf57e4896a251bc4"


# ── JWT 생성 ─────────────────────────────────────────────────────────────
def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def generate_token(hwid: str, expire_days: int) -> str:
    """HWID + 유효기간(일)으로 HS256 JWT 생성. admin_issued=True 포함."""
    header  = _b64(json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64(json.dumps({
        "hwid":         hwid.strip().upper(),
        "exp":          int(time.time()) + expire_days * 86400,
        "iat":          int(time.time()),
        "admin_issued": True,
    }, separators=(",", ":")).encode())
    sig = _b64(hmac.new(
        _JWT_SECRET.encode(),
        f"{header}.{payload}".encode(),
        hashlib.sha256,
    ).digest())
    return f"{header}.{payload}.{sig}"


def build_license_dat(hwid: str, expire_days: int, note: str = "") -> dict:
    """license.dat JSON 내용 생성."""
    token = generate_token(hwid, expire_days)
    return {
        "token":       token,
        "license_key": note or f"ADMIN-{hwid[:8]}",
        "hwid":        hwid.strip().upper(),
        "last_online": time.time(),   # 이미 확인된 것으로 간주 → 즉시 재확인 방지
    }


# ── GUI ──────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("MapleBot 라이선스 발급기 (관리자)")
        self.resizable(False, False)
        self._build()

    def _build(self):
        pad = {"padx": 10, "pady": 5}

        # ── HWID 입력 ──────────────────────────────────────────────────
        tk.Label(self, text="HWID (16자리)", anchor="w").grid(row=0, column=0, sticky="w", **pad)
        self._hwid_var = tk.StringVar()
        tk.Entry(self, textvariable=self._hwid_var, width=22, font=("Courier", 12)).grid(
            row=0, column=1, **pad)

        # ── 유효기간 ───────────────────────────────────────────────────
        tk.Label(self, text="유효기간 (일)", anchor="w").grid(row=1, column=0, sticky="w", **pad)
        self._days_var = tk.StringVar(value="30")
        frame_days = tk.Frame(self)
        frame_days.grid(row=1, column=1, sticky="w", **pad)
        tk.Entry(frame_days, textvariable=self._days_var, width=6).pack(side="left")
        for label, days in [("30일", 30), ("90일", 90), ("180일", 180), ("365일", 365), ("무제한", 36500)]:
            tk.Button(frame_days, text=label, width=5,
                      command=lambda d=days: self._days_var.set(str(d))).pack(side="left", padx=2)

        # ── 메모 (선택) ────────────────────────────────────────────────
        tk.Label(self, text="메모 (선택)", anchor="w").grid(row=2, column=0, sticky="w", **pad)
        self._note_var = tk.StringVar()
        tk.Entry(self, textvariable=self._note_var, width=30).grid(row=2, column=1, **pad)

        # ── 만료일 표시 ────────────────────────────────────────────────
        self._expire_lbl = tk.Label(self, text="", fg="gray")
        self._expire_lbl.grid(row=3, column=0, columnspan=2, **pad)
        self._days_var.trace_add("write", self._update_expire_label)
        self._update_expire_label()

        # ── 발급 버튼 ─────────────────────────────────────────────────
        tk.Button(self, text="🔑  라이선스 발급", command=self._generate,
                  bg="#4CAF50", fg="white", font=("", 11, "bold"),
                  height=2, width=20).grid(row=4, column=0, columnspan=2, pady=10)

        # ── 결과 출력 ─────────────────────────────────────────────────
        tk.Label(self, text="생성된 license.dat 내용", anchor="w").grid(
            row=5, column=0, columnspan=2, sticky="w", padx=10)
        self._result = tk.Text(self, width=64, height=8, font=("Courier", 8), state="disabled")
        self._result.grid(row=6, column=0, columnspan=2, padx=10, pady=5)

        # ── 버튼들 ────────────────────────────────────────────────────
        btn_frame = tk.Frame(self)
        btn_frame.grid(row=7, column=0, columnspan=2, pady=(0, 10))
        tk.Button(btn_frame, text="📋 클립보드 복사", command=self._copy, width=15).pack(
            side="left", padx=5)
        tk.Button(btn_frame, text="💾 파일 저장", command=self._save, width=15).pack(
            side="left", padx=5)

    def _update_expire_label(self, *_):
        try:
            days = int(self._days_var.get())
            expire = datetime.now() + timedelta(days=days)
            self._expire_lbl.config(text=f"만료일: {expire.strftime('%Y-%m-%d')}  ({days}일)")
        except ValueError:
            self._expire_lbl.config(text="")

    def _generate(self):
        hwid = self._hwid_var.get().strip().upper()
        if len(hwid) != 16 or not hwid.isalnum():
            messagebox.showerror("오류", "HWID는 영숫자 16자리여야 합니다.")
            return
        try:
            days = int(self._days_var.get())
            if days <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("오류", "유효기간은 양의 정수(일)를 입력하세요.")
            return

        dat = build_license_dat(hwid, days, self._note_var.get().strip())
        pretty = json.dumps(dat, ensure_ascii=False, indent=2)
        self._result.config(state="normal")
        self._result.delete("1.0", "end")
        self._result.insert("1.0", pretty)
        self._result.config(state="disabled")
        self._last_json = pretty
        messagebox.showinfo("완료", f"✅ 라이선스 발급 완료\nHWID: {hwid}\n만료일: "
                            f"{(datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')}")

    def _copy(self):
        txt = getattr(self, "_last_json", "")
        if not txt:
            messagebox.showwarning("알림", "먼저 라이선스를 발급하세요.")
            return
        self.clipboard_clear()
        self.clipboard_append(txt)
        messagebox.showinfo("복사됨", "클립보드에 복사되었습니다.")

    def _save(self):
        txt = getattr(self, "_last_json", "")
        if not txt:
            messagebox.showwarning("알림", "먼저 라이선스를 발급하세요.")
            return
        hwid = self._hwid_var.get().strip().upper()
        path = filedialog.asksaveasfilename(
            defaultextension=".dat",
            initialfile=f"license_{hwid}.dat",
            filetypes=[("DAT 파일", "*.dat"), ("모든 파일", "*.*")],
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(txt)
            messagebox.showinfo("저장됨", f"저장 완료:\n{path}")


if __name__ == "__main__":
    App().mainloop()
