from __future__ import annotations

import base64
import json
import tkinter as tk
from tkinter import messagebox, ttk

from app.core.signer import sign_bytes
from app.services.crypto_service import CryptoService


class SignTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=12)
        self.app = app

        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        ttk.Label(self, text="Detached Sign", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        form = ttk.Frame(self)
        form.grid(row=1, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Profile").grid(row=0, column=0, sticky="w")
        self.profile_cb = ttk.Combobox(form, state="readonly")
        self.profile_cb.grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(form, text="Message").grid(row=1, column=0, sticky="nw")
        self.message_box = tk.Text(self, height=10, wrap="word")
        self.message_box.grid(row=2, column=0, sticky="nsew", pady=(8, 10))

        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        ttk.Button(actions, text="Sign message", command=self.sign_message).pack(side="left")

        self.output_box = tk.Text(self, wrap="word", height=12)
        self.output_box.grid(row=4, column=0, sticky="nsew")

    def refresh_choices(self):
        self.profile_cb["values"] = self.app.profiles_cache
        if self.app.profiles_cache and not self.profile_cb.get():
            self.profile_cb.current(0)

    def sign_message(self):
        profile_name = self.profile_cb.get().strip()
        message = self.message_box.get("1.0", tk.END).rstrip("\n")

        if not profile_name:
            messagebox.showwarning("Warning", "Cần chọn profile.")
            return
        if not message:
            messagebox.showwarning("Warning", "Message đang trống.")
            return

        try:
            profile = self.app.key_service.load_profile(profile_name)
            private_key_b64 = self.app.crypto_service._get_ed25519_private_key_b64(profile)
            private_key = self.app.crypto_service._load_ed25519_private_key_from_b64(private_key_b64)

            signature = sign_bytes(private_key, message.encode("utf-8"))

            result = {
                "profile": profile_name,
                "message": message,
                "signature_b64": base64.b64encode(signature).decode("utf-8"),
            }

            self.output_box.delete("1.0", tk.END)
            self.output_box.insert("1.0", json.dumps(result, indent=2, ensure_ascii=False))
            self.app.set_status("Ký message thành công.")
        except Exception as exc:
            messagebox.showerror("Sign error", str(exc))
            self.app.set_status("Ký message thất bại.")