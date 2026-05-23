# 관리자용 라이선스 발급/관리 도구 (빌드 제외)
from __future__ import annotations
import json
import os
import sys
import time
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timedelta, timezone

# ── Supabase 설정 (license_manager.py 와 동일) ──────────────────────────
_PROJECT  = "djdpfwoolwqrasqretng"
_ANON_KEY = "sb_publishable_qUnX4JoLF1MqNzjZGSURmQ_HerOiHZr"
_BASE_URL = f"https://{_PROJECT}.supabase.co"

# 서비스 롤 키 (Supabase Dashboard → Settings → API → service_role)
# 처음 실행 시 입력 창이 나옵니다.
_SERVICE_KEY_FILE = os.path.join(os.path.dirname(__file__), ".service_key")

# ── HWID (현재 PC) ───────────────────────────────────────────────────────
def _get_hwid() -> str:
    try:
        sys.path.insert(0, os.path.dirname(__file__))
        from core.hw_fingerprint import get_hwid
        return get_hwid()
    except Exception:
        return "UNKNOWN"


# ── Supabase 호출 헬퍼 ──────────────────────────────────────────────────
def _headers(service: bool = False) -> dict:
    key = _load_service_key() if service else _ANON_KEY
    return {
        "apikey":        key,
        "Authorization": f"Bearer {key}",
        "Content-Type":  "application/json",
    }

def _load_service_key() -> str:
    if os.path.exists(_SERVICE_KEY_FILE):
        with open(_SERVICE_KEY_FILE) as f:
            return f.read().strip()
    return ""

def _save_service_key(key: str) -> None:
    with open(_SERVICE_KEY_FILE, "w") as f:
        f.write(key.strip())


def generate_license(name: str, days: int) -> dict:
    """generate Edge Function 호출 → 라이선스 키 반환."""
    import requests
    expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    resp = requests.post(
        f"{_BASE_URL}/functions/v1/generate",
        headers=_headers(service=True),
        json={"expires_at": expires_at, "note": name},
        timeout=10,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"서버 오류 {resp.status_code}: {resp.text}")
    return resp.json()


def fetch_licenses() -> list[dict]:
    """Supabase REST API로 licenses 테이블 전체 조회."""
    import requests
    resp = requests.get(
        f"{_BASE_URL}/rest/v1/licenses?select=*&order=created_at.desc",
        headers=_headers(service=True),
        timeout=10,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"조회 실패 {resp.status_code}: {resp.text}")
    return resp.json()


def revoke_license(key: str) -> None:
    """licenses 테이블에서 해당 키 삭제."""
    import requests
    resp = requests.delete(
        f"{_BASE_URL}/rest/v1/licenses?key=eq.{key}",
        headers=_headers(service=True),
        timeout=10,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"삭제 실패 {resp.status_code}: {resp.text}")


# ── 날짜 포매팅 ──────────────────────────────────────────────────────────
def _fmt_dt(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return iso[:10]

def _days_left(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone()
        d  = (dt - datetime.now().astimezone()).days
        return f"D-{d}" if d >= 0 else "만료"
    except Exception:
        return "-"


# ── 메인 UI ──────────────────────────────────────────────────────────────
class App(tk.Tk):
    COLS = ("이름/메모", "라이선스 키", "활성화", "HWID", "발급일", "만료일", "남은일")
    COL_W = (110, 200, 60, 140, 90, 90, 70)

    def __init__(self):
        super().__init__()
        self.title("MapleBot 라이선스 관리")
        self.geometry("860x520")
        self.minsize(760, 440)
        self._hwid = _get_hwid()
        self._rows: list[dict] = []
        self._build()
        self._check_service_key()

    # ── UI 구성 ─────────────────────────────────────────────────────────
    def _build(self):
        # ── 상단 헤더 ─────────────────────────────────────────────────
        hdr = tk.Frame(self, bg="#1e1e2e", pady=8)
        hdr.pack(fill="x")
        tk.Label(hdr, text="MapleBot  라이선스 관리", bg="#1e1e2e",
                 fg="white", font=("", 13, "bold")).pack(side="left", padx=14)
        tk.Label(hdr, text=f"현재 PC HWID: {self._hwid}",
                 bg="#1e1e2e", fg="#aaaacc", font=("Courier", 10)).pack(side="right", padx=14)

        # ── 발급 폼 ───────────────────────────────────────────────────
        form = tk.Frame(self, pady=6, padx=10)
        form.pack(fill="x")

        tk.Label(form, text="이름/메모").grid(row=0, column=0, sticky="w", padx=(0, 4))
        self._name_var = tk.StringVar()
        tk.Entry(form, textvariable=self._name_var, width=18).grid(row=0, column=1, padx=4)

        tk.Label(form, text="유효기간").grid(row=0, column=2, sticky="w", padx=(12, 4))
        self._days_var = tk.StringVar(value="30")
        days_cb = ttk.Combobox(form, textvariable=self._days_var, width=8,
                               values=["7", "30", "60", "90", "180", "365", "36500"])
        days_cb.grid(row=0, column=3, padx=4)
        tk.Label(form, text="일").grid(row=0, column=4, sticky="w")

        self._expire_lbl = tk.Label(form, text="", fg="gray", font=("", 9))
        self._expire_lbl.grid(row=0, column=5, padx=8)
        self._days_var.trace_add("write", self._update_expire)
        self._update_expire()

        self._btn_issue = tk.Button(form, text="+ 라이선스 발급",
                                    command=self._on_issue,
                                    bg="#4CAF50", fg="white", font=("", 10, "bold"),
                                    padx=10, pady=2)
        self._btn_issue.grid(row=0, column=6, padx=(16, 0))

        # ── 리스트 (Treeview) ─────────────────────────────────────────
        list_frame = tk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10, pady=6)

        self._tree = ttk.Treeview(list_frame, columns=self.COLS,
                                  show="headings", selectmode="browse")
        for col, w in zip(self.COLS, self.COL_W):
            self._tree.heading(col, text=col)
            self._tree.column(col, width=w, anchor="center", minwidth=40)
        self._tree.column("이름/메모", anchor="w")
        self._tree.column("라이선스 키", anchor="w")
        self._tree.column("HWID", anchor="w")

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scroll.set)
        self._tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # 행 색상
        self._tree.tag_configure("activated", background="#e8f5e9")
        self._tree.tag_configure("expired",   background="#ffebee", foreground="#c62828")
        self._tree.tag_configure("unused",    background="#ffffff")

        self._tree.bind("<Double-1>", self._on_double_click)

        # ── 하단 버튼 ─────────────────────────────────────────────────
        btn_bar = tk.Frame(self, pady=6)
        btn_bar.pack(fill="x", padx=10)

        tk.Button(btn_bar, text="📋 키 복사", command=self._copy_key,
                  width=12).pack(side="left", padx=4)
        tk.Button(btn_bar, text="🗑 삭제/취소", command=self._revoke,
                  width=12, fg="red").pack(side="left", padx=4)
        tk.Button(btn_bar, text="🔄 새로고침", command=self._refresh,
                  width=12).pack(side="left", padx=4)

        self._status = tk.Label(btn_bar, text="", fg="gray", anchor="w")
        self._status.pack(side="left", padx=12)

        tk.Label(btn_bar, text="🔑 서비스 키 변경",
                 fg="blue", cursor="hand2").pack(side="right", padx=8)
        btn_bar.winfo_children()[-1].bind("<Button-1>", lambda _: self._ask_service_key())

    # ── 유효기간 라벨 업데이트 ─────────────────────────────────────────
    def _update_expire(self, *_):
        try:
            d = int(self._days_var.get())
            exp = (datetime.now() + timedelta(days=d)).strftime("%Y-%m-%d")
            self._expire_lbl.config(text=f"→ 만료 {exp}")
        except ValueError:
            self._expire_lbl.config(text="")

    # ── 서비스 키 확인/입력 ───────────────────────────────────────────
    def _check_service_key(self):
        if not _load_service_key():
            self.after(200, self._ask_service_key)
        else:
            self.after(300, self._refresh)

    def _ask_service_key(self):
        dlg = tk.Toplevel(self)
        dlg.title("Supabase 서비스 롤 키 입력")
        dlg.geometry("520x140")
        dlg.grab_set()
        tk.Label(dlg, text="Supabase Dashboard → Settings → API → service_role 키",
                 wraplength=480).pack(padx=16, pady=(14, 4))
        var = tk.StringVar(value=_load_service_key())
        ent = tk.Entry(dlg, textvariable=var, width=60, show="*")
        ent.pack(padx=16)
        def _save():
            k = var.get().strip()
            if not k:
                return
            _save_service_key(k)
            dlg.destroy()
            self._refresh()
        tk.Button(dlg, text="저장", command=_save,
                  bg="#4CAF50", fg="white", width=12).pack(pady=10)
        ent.focus()

    # ── 라이선스 발급 ─────────────────────────────────────────────────
    def _on_issue(self):
        name = self._name_var.get().strip()
        if not name:
            messagebox.showwarning("입력 오류", "이름/메모를 입력하세요.", parent=self)
            return
        try:
            days = int(self._days_var.get())
            if days <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("입력 오류", "유효기간은 양의 정수를 입력하세요.", parent=self)
            return

        self._btn_issue.config(state="disabled", text="발급 중...")
        self._set_status("서버에 발급 요청 중...")

        def _do():
            try:
                result = generate_license(name, days)
                key = result.get("key", result.get("license_key", ""))
                self.after(0, lambda: self._issue_done(key, name, days))
            except Exception as e:
                self.after(0, lambda: self._issue_error(str(e)))

        threading.Thread(target=_do, daemon=True).start()

    def _issue_done(self, key: str, name: str, days: int):
        self._btn_issue.config(state="normal", text="+ 라이선스 발급")
        if not key:
            messagebox.showerror("오류", "서버 응답에서 키를 찾을 수 없습니다.", parent=self)
            return
        # 클립보드에 즉시 복사
        self.clipboard_clear()
        self.clipboard_append(key)
        self._set_status(f"✅ 발급 완료 — 클립보드에 복사됨")
        messagebox.showinfo("발급 완료",
                            f"라이선스 키가 발급되었습니다.\n\n"
                            f"  {key}\n\n"
                            f"클립보드에 복사되었습니다.\n"
                            f"사용자에게 이 키를 전달하세요.",
                            parent=self)
        self._name_var.set("")
        self._refresh()

    def _issue_error(self, msg: str):
        self._btn_issue.config(state="normal", text="+ 라이선스 발급")
        self._set_status(f"❌ 발급 실패")
        messagebox.showerror("발급 실패", msg, parent=self)

    # ── 목록 새로고침 ────────────────────────────────────────────────
    def _refresh(self):
        self._set_status("불러오는 중...")
        def _do():
            try:
                rows = fetch_licenses()
                self.after(0, lambda: self._populate(rows))
            except Exception as e:
                self.after(0, lambda: self._set_status(f"❌ 조회 실패: {e}"))
        threading.Thread(target=_do, daemon=True).start()

    def _populate(self, rows: list[dict]):
        self._rows = rows
        for item in self._tree.get_children():
            self._tree.delete(item)

        for r in rows:
            activated = r.get("activated", False)
            hwid      = r.get("hwid", "") or ""
            note      = r.get("note", r.get("key", "")[:8])
            key       = r.get("key", "")
            created   = _fmt_dt(r.get("created_at"))
            expires   = _fmt_dt(r.get("expires_at"))
            left      = _days_left(r.get("expires_at"))

            tag = "activated" if activated else ("expired" if left == "만료" else "unused")
            act_txt = "✅ 활성" if activated else "⬜ 미사용"

            self._tree.insert("", "end",
                              values=(note, key, act_txt, hwid or "-", created, expires, left),
                              tags=(tag,), iid=key)

        total = len(rows)
        act   = sum(1 for r in rows if r.get("activated"))
        self._set_status(f"총 {total}개  |  활성화 {act}개  |  미사용 {total - act}개")

    # ── 키 복사 ─────────────────────────────────────────────────────
    def _copy_key(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("알림", "목록에서 항목을 선택하세요.", parent=self)
            return
        key = sel[0]   # iid = key
        self.clipboard_clear()
        self.clipboard_append(key)
        self._set_status(f"📋 클립보드 복사됨: {key}")

    def _on_double_click(self, _):
        self._copy_key()

    # ── 삭제/취소 ────────────────────────────────────────────────────
    def _revoke(self):
        sel = self._tree.selection()
        if not sel:
            messagebox.showinfo("알림", "목록에서 항목을 선택하세요.", parent=self)
            return
        key = sel[0]
        if not messagebox.askyesno("삭제 확인",
                                   f"아래 라이선스를 삭제하시겠습니까?\n\n{key}",
                                   parent=self):
            return
        self._set_status("삭제 중...")
        def _do():
            try:
                revoke_license(key)
                self.after(0, self._refresh)
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("삭제 실패", str(e), parent=self))
        threading.Thread(target=_do, daemon=True).start()

    def _set_status(self, msg: str):
        self._status.config(text=msg)


if __name__ == "__main__":
    App().mainloop()
