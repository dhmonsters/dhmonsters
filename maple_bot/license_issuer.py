# 라이선스 v2 관리자 발급기 UI.
from __future__ import annotations

import os
import threading
import tkinter as tk
from datetime import datetime, timedelta, timezone
from tkinter import messagebox, ttk

PROJECT_REF = "djdpfwoolwqrasqretng"
ANON_KEY = "sb_publishable_qUnX4JoLF1MqNzjZGSURmQ_HerOiHZr"
BASE_URL = f"https://{PROJECT_REF}.supabase.co"

ROOT_DIR = os.path.dirname(__file__)
ADMIN_KEY_FILE = os.path.join(ROOT_DIR, ".admin_key")


def _load_admin_key() -> str:
    if os.path.exists(ADMIN_KEY_FILE):
        with open(ADMIN_KEY_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def _save_admin_key(key: str) -> None:
    with open(ADMIN_KEY_FILE, "w", encoding="utf-8") as f:
        f.write(key.strip())


def _headers() -> dict[str, str]:
    admin_key = _load_admin_key()
    return {
        "apikey": ANON_KEY,
        "Authorization": f"Bearer {ANON_KEY}",
        "Content-Type": "application/json",
        "X-Admin-Key": admin_key,
    }


def _fmt_date(value: str | None) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return value[:10]


def _days_left(value: str | None) -> str:
    if not value:
        return "-"
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone()
        days = (dt - datetime.now().astimezone()).days
        return f"D-{days}" if days >= 0 else "만료"
    except Exception:
        return "-"


def generate_license(name: str, email: str, days: int) -> str:
    import requests

    expires_at = (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()
    resp = requests.post(
        f"{BASE_URL}/functions/v1/generate",
        headers=_headers(),
        json={
            "name": name,
            "email": email or None,
            "expires_at": expires_at,
        },
        timeout=12,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"발급 실패 {resp.status_code}: {resp.text}")
    data = resp.json()
    key = str(data.get("key", "")).strip()
    if not key:
        raise RuntimeError(f"서버 응답에 라이선스 키가 없습니다: {data}")
    return key


def fetch_licenses() -> list[dict]:
    import requests

    resp = requests.post(
        f"{BASE_URL}/functions/v1/license-admin",
        headers=_headers(),
        json={"action": "list"},
        timeout=12,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"조회 실패 {resp.status_code}: {resp.text}")
    data = resp.json()
    if not isinstance(data, list):
        raise RuntimeError(f"목록 응답이 올바르지 않습니다: {data}")
    return data


def revoke_license(key_hint: str) -> None:
    import requests

    resp = requests.post(
        f"{BASE_URL}/functions/v1/license-admin",
        headers=_headers(),
        json={"action": "revoke", "key_hint": key_hint},
        timeout=12,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"취소 실패 {resp.status_code}: {resp.text}")


def extend_license(key_hint: str, days: int) -> None:
    import requests

    resp = requests.post(
        f"{BASE_URL}/functions/v1/license-admin",
        headers=_headers(),
        json={"action": "extend", "key_hint": key_hint, "days": days},
        timeout=12,
    )
    if resp.status_code not in (200, 204):
        raise RuntimeError(f"연장 실패 {resp.status_code}: {resp.text}")


class LicenseIssuerApp(tk.Tk):
    COLUMNS = ("name", "key", "status", "activated", "hwid", "created_at", "expires_at", "left")
    HEADERS = {
        "name": "이름/메모",
        "key": "라이선스",
        "status": "상태",
        "activated": "활성화",
        "hwid": "HWID",
        "created_at": "발급일",
        "expires_at": "만료일",
        "left": "남은 기간",
    }
    WIDTHS = {
        "name": 140,
        "key": 150,
        "status": 80,
        "activated": 70,
        "hwid": 130,
        "created_at": 90,
        "expires_at": 90,
        "left": 80,
    }

    def __init__(self) -> None:
        super().__init__()
        self.title("Claude 라이선스 v2 발급기")
        self.geometry("920x560")
        self.minsize(820, 460)
        self._rows: list[dict] = []
        self._build_ui()
        self.after(200, self._ensure_admin_key)

    def _build_ui(self) -> None:
        header = tk.Frame(self, bg="#173f3a", pady=10)
        header.pack(fill="x")
        tk.Label(
            header,
            text="Claude 라이선스 v2 발급기",
            bg="#173f3a",
            fg="white",
            font=("", 14, "bold"),
        ).pack(side="left", padx=14)
        tk.Label(
            header,
            text=f"Project: {PROJECT_REF}",
            bg="#173f3a",
            fg="#cfe7e2",
            font=("Courier", 9),
        ).pack(side="right", padx=14)

        form = tk.Frame(self, padx=10, pady=8)
        form.pack(fill="x")

        tk.Label(form, text="이름/메모").grid(row=0, column=0, sticky="w")
        self.name_var = tk.StringVar()
        tk.Entry(form, textvariable=self.name_var, width=18).grid(row=0, column=1, padx=(4, 12))

        tk.Label(form, text="이메일").grid(row=0, column=2, sticky="w")
        self.email_var = tk.StringVar()
        tk.Entry(form, textvariable=self.email_var, width=24).grid(row=0, column=3, padx=(4, 12))

        tk.Label(form, text="기간").grid(row=0, column=4, sticky="w")
        self.days_var = tk.StringVar(value="30")
        ttk.Combobox(
            form,
            textvariable=self.days_var,
            values=["7", "30", "60", "90", "180", "365", "36500"],
            width=8,
        ).grid(row=0, column=5, padx=(4, 2))
        tk.Label(form, text="일").grid(row=0, column=6, sticky="w")

        self.expire_label = tk.Label(form, text="", fg="gray")
        self.expire_label.grid(row=0, column=7, padx=10)
        self.days_var.trace_add("write", self._update_expire_label)
        self._update_expire_label()

        self.issue_button = tk.Button(
            form,
            text="+ 라이선스 발급",
            command=self._issue,
            bg="#087f6f",
            fg="white",
            padx=10,
        )
        self.issue_button.grid(row=0, column=8, padx=(14, 0))

        list_frame = tk.Frame(self)
        list_frame.pack(fill="both", expand=True, padx=10, pady=6)

        self.tree = ttk.Treeview(list_frame, columns=self.COLUMNS, show="headings", selectmode="browse")
        for col in self.COLUMNS:
            self.tree.heading(col, text=self.HEADERS[col])
            self.tree.column(col, width=self.WIDTHS[col], anchor="center")
        self.tree.column("name", anchor="w")
        self.tree.column("key", anchor="w")
        self.tree.column("hwid", anchor="w")
        self.tree.tag_configure("active", background="#e8f5e9")
        self.tree.tag_configure("revoked", background="#f3f3f3", foreground="#777777")
        self.tree.tag_configure("expired", background="#ffebee", foreground="#b71c1c")
        self.tree.bind("<Double-1>", lambda _: self._copy_selected_key())

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        bar = tk.Frame(self, padx=10, pady=8)
        bar.pack(fill="x")
        tk.Button(bar, text="키 복사", command=self._copy_selected_key, width=12).pack(side="left", padx=3)
        tk.Button(bar, text="라이선스 취소", command=self._revoke_selected, width=12, fg="red").pack(side="left", padx=3)
        tk.Button(bar, text="+30일", command=lambda: self._extend_selected(30), width=8).pack(side="left", padx=3)
        tk.Button(bar, text="+90일", command=lambda: self._extend_selected(90), width=8).pack(side="left", padx=3)
        tk.Button(bar, text="+365일", command=lambda: self._extend_selected(365), width=8).pack(side="left", padx=3)
        tk.Button(bar, text="새로고침", command=self._refresh, width=12).pack(side="left", padx=3)
        tk.Button(bar, text="Admin Key 설정", command=self._ask_admin_key, width=14).pack(side="right", padx=3)
        self.status_label = tk.Label(bar, text="", fg="gray", anchor="w")
        self.status_label.pack(side="left", padx=12)

    def _ensure_admin_key(self) -> None:
        if not _load_admin_key():
            self._ask_admin_key()
        else:
            self._refresh()

    def _ask_admin_key(self) -> None:
        dlg = tk.Toplevel(self)
        dlg.title("Admin Key 설정")
        dlg.geometry("560x145")
        dlg.grab_set()
        tk.Label(dlg, text="CLAUDE_LICENSE_ADMIN_KEY 값을 입력하세요.", anchor="w").pack(fill="x", padx=16, pady=(16, 4))
        key_var = tk.StringVar(value=_load_admin_key())
        entry = tk.Entry(dlg, textvariable=key_var, width=68, show="*")
        entry.pack(fill="x", padx=16)
        entry.focus_set()

        def save() -> None:
            key = key_var.get().strip()
            if not key:
                messagebox.showwarning("입력 필요", "Admin Key를 입력하세요.", parent=dlg)
                return
            _save_admin_key(key)
            dlg.destroy()
            self._refresh()

        tk.Button(dlg, text="저장", command=save, bg="#087f6f", fg="white", width=12).pack(pady=14)

    def _update_expire_label(self, *_args) -> None:
        try:
            days = int(self.days_var.get())
            exp = (datetime.now() + timedelta(days=days)).strftime("%Y-%m-%d")
            self.expire_label.config(text=f"만료 예정: {exp}")
        except Exception:
            self.expire_label.config(text="")

    def _issue(self) -> None:
        name = self.name_var.get().strip()
        email = self.email_var.get().strip()
        if not name:
            messagebox.showwarning("입력 필요", "이름/메모를 입력하세요.", parent=self)
            return
        try:
            days = int(self.days_var.get())
            if days <= 0:
                raise ValueError
        except ValueError:
            messagebox.showerror("입력 오류", "기간은 1 이상의 숫자여야 합니다.", parent=self)
            return
        self.issue_button.config(state="disabled", text="발급 중...")
        self._set_status("서버에 라이선스 발급 요청 중...")

        def worker() -> None:
            try:
                key = generate_license(name, email, days)
                self.after(0, lambda: self._issue_done(key))
            except Exception as exc:
                self.after(0, lambda: self._issue_error(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _issue_done(self, key: str) -> None:
        self.issue_button.config(state="normal", text="+ 라이선스 발급")
        self.clipboard_clear()
        self.clipboard_append(key)
        self._set_status("발급 완료. 키를 클립보드에 복사했습니다.")
        messagebox.showinfo("발급 완료", f"라이선스 키가 발급되었습니다.\n\n{key}\n\n클립보드에 복사했습니다.", parent=self)
        self.name_var.set("")
        self.email_var.set("")
        self._refresh()

    def _issue_error(self, message: str) -> None:
        self.issue_button.config(state="normal", text="+ 라이선스 발급")
        self._set_status("발급 실패")
        messagebox.showerror("발급 실패", message, parent=self)

    def _refresh(self) -> None:
        self._set_status("목록을 불러오는 중...")

        def worker() -> None:
            try:
                rows = fetch_licenses()
                self.after(0, lambda: self._populate(rows))
            except Exception as exc:
                self.after(0, lambda: self._set_status(f"조회 실패: {exc}"))

        threading.Thread(target=worker, daemon=True).start()

    def _populate(self, rows: list[dict]) -> None:
        self._rows = rows
        for item in self.tree.get_children():
            self.tree.delete(item)
        for row in rows:
            key_hint = str(row.get("key", ""))
            status = str(row.get("status", ""))
            activated = "예" if row.get("activated") else "아니오"
            left = _days_left(row.get("expires_at"))
            tag = "expired" if left == "만료" else ("revoked" if status == "revoked" else "active")
            self.tree.insert(
                "",
                "end",
                iid=key_hint,
                values=(
                    row.get("name", ""),
                    key_hint,
                    status,
                    activated,
                    row.get("hwid", "") or "-",
                    _fmt_date(row.get("created_at")),
                    _fmt_date(row.get("expires_at")),
                    left,
                ),
                tags=(tag,),
            )
        active_count = sum(1 for row in rows if row.get("activated"))
        self._set_status(f"총 {len(rows)}개. 활성화 {active_count}개.")

    def _selected_key_hint(self) -> str | None:
        selected = self.tree.selection()
        return selected[0] if selected else None

    def _copy_selected_key(self) -> None:
        key_hint = self._selected_key_hint()
        if not key_hint:
            messagebox.showinfo("알림", "목록에서 라이선스를 선택하세요.", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append(key_hint)
        self._set_status(f"키 힌트를 복사했습니다: {key_hint}")

    def _revoke_selected(self) -> None:
        key_hint = self._selected_key_hint()
        if not key_hint:
            messagebox.showinfo("알림", "목록에서 라이선스를 선택하세요.", parent=self)
            return
        if not messagebox.askyesno("취소 확인", f"이 라이선스를 취소할까요?\n\n{key_hint}", parent=self):
            return
        self._set_status("라이선스 취소 중...")

        def worker() -> None:
            try:
                revoke_license(key_hint)
                self.after(0, self._refresh)
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("취소 실패", str(exc), parent=self))

        threading.Thread(target=worker, daemon=True).start()

    def _extend_selected(self, days: int) -> None:
        key_hint = self._selected_key_hint()
        if not key_hint:
            messagebox.showinfo("알림", "목록에서 라이선스를 선택하세요.", parent=self)
            return
        if not messagebox.askyesno("연장 확인", f"이 라이선스를 {days}일 연장할까요?\n\n{key_hint}", parent=self):
            return
        self._set_status(f"라이선스 {days}일 연장 중...")

        def worker() -> None:
            try:
                extend_license(key_hint, days)
                self.after(0, self._refresh)
            except Exception as exc:
                self.after(0, lambda: messagebox.showerror("연장 실패", str(exc), parent=self))

        threading.Thread(target=worker, daemon=True).start()

    def _set_status(self, message: str) -> None:
        self.status_label.config(text=message)


if __name__ == "__main__":
    LicenseIssuerApp().mainloop()
