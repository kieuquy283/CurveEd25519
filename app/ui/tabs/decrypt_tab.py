from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


class DecryptTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=12)
        self.app = app
        self.envelope_var = tk.StringVar()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        ttk.Label(self, text="Decrypt + Verify", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        form = ttk.Frame(self)
        form.grid(row=1, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Recipient profile").grid(row=0, column=0, sticky="w")
        self.profile_cb = ttk.Combobox(form, state="readonly")
        self.profile_cb.grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(form, text="Envelope file").grid(row=1, column=0, sticky="w")
        ttk.Entry(form, textvariable=self.envelope_var).grid(row=1, column=1, sticky="ew", padx=8, pady=4)
        ttk.Button(form, text="Browse", command=self.pick_envelope).grid(row=1, column=2)

        actions = ttk.Frame(self)
        actions.grid(row=2, column=0, sticky="ew", pady=(8, 10))
        ttk.Button(actions, text="Decrypt", command=self.decrypt_message).pack(side="left")
        ttk.Button(actions, text="Save plaintext", command=self.save_plaintext).pack(side="left", padx=6)

        self.output_box = tk.Text(self, wrap="word")
        self.output_box.grid(row=3, column=0, sticky="nsew")

        self.last_plaintext: bytes | None = None

    def refresh_choices(self):
        self.profile_cb["values"] = self.app.profiles_cache
        if self.app.profiles_cache and not self.profile_cb.get():
            self.profile_cb.current(0)

    def pick_envelope(self):
        file_path = filedialog.askopenfilename(
            title="Chọn encrypted envelope",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if file_path:
            self.envelope_var.set(file_path)

    def decrypt_message(self):
        profile_name = self.profile_cb.get().strip()
        envelope_path = self.envelope_var.get().strip()

        if not profile_name:
            messagebox.showwarning("Warning", "Cần chọn recipient profile.")
            return
        if not envelope_path:
            messagebox.showwarning("Warning", "Cần chọn file envelope.")
            return

        try:
            receiver_profile = self.app.key_service.load_profile(profile_name)
            envelope = json.loads(Path(envelope_path).read_text(encoding="utf-8"))

            sender_contact = None
            sender_name = envelope.get("header", {}).get("sender", {}).get("name")
            if sender_name and sender_name in self.app.contacts_cache:
                sender_contact = self.app.key_service.load_contact(sender_name)

            result = self.app.crypto_service.decrypt_message(
                receiver_profile=receiver_profile,
                envelope=envelope,
                sender_contact=sender_contact,
                verify_before_decrypt=True,
                include_debug=True,
            )

            self.output_box.delete("1.0", tk.END)

            if "plaintext" in result:
                self.last_plaintext = result["plaintext"].encode("utf-8")
                self.output_box.insert("1.0", result["plaintext"] + "\n\n")
            elif "plaintext_bytes_b64" in result:
                self.last_plaintext = None
                self.output_box.insert("1.0", "<binary plaintext>\n\n")

            self.output_box.insert(
                tk.END,
                json.dumps(result, indent=2, ensure_ascii=False, default=str),
            )

            self.app.set_status("Decrypt thành công.")
        except Exception as exc:
            self.last_plaintext = None
            messagebox.showerror("Decrypt error", str(exc))
            self.app.set_status("Decrypt thất bại.")

    def save_plaintext(self):
        if not self.last_plaintext:
            messagebox.showwarning("Warning", "Chưa có plaintext text để lưu.")
            return

        out_path = filedialog.asksaveasfilename(
            title="Save plaintext",
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile="plaintext.txt",
        )
        if not out_path:
            return

        Path(out_path).write_bytes(self.last_plaintext)
        self.app.set_status("Đã lưu plaintext.")
        messagebox.showinfo("Success", f"Đã lưu plaintext:\n{out_path}")