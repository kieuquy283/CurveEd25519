from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


class EncryptTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=12)
        self.app = app
        self.input_mode = tk.StringVar(value="text")
        self.input_file_var = tk.StringVar()

        self.columnconfigure(0, weight=1)
        self.rowconfigure(4, weight=1)

        ttk.Label(self, text="Encrypt + Sign", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        form = ttk.Frame(self)
        form.grid(row=1, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        ttk.Label(form, text="Sender profile").grid(row=0, column=0, sticky="w")
        self.sender_cb = ttk.Combobox(form, state="readonly")
        self.sender_cb.grid(row=0, column=1, sticky="ew", padx=8, pady=4)

        ttk.Label(form, text="Recipient contact").grid(row=1, column=0, sticky="w")
        self.recipient_cb = ttk.Combobox(form, state="readonly")
        self.recipient_cb.grid(row=1, column=1, sticky="ew", padx=8, pady=4)

        mode_frame = ttk.Frame(form)
        mode_frame.grid(row=2, column=0, columnspan=2, sticky="w", pady=6)
        ttk.Radiobutton(mode_frame, text="Text", variable=self.input_mode, value="text", command=self.toggle_mode).pack(side="left")
        ttk.Radiobutton(mode_frame, text="File", variable=self.input_mode, value="file", command=self.toggle_mode).pack(side="left", padx=8)

        self.file_frame = ttk.Frame(form)
        self.file_frame.grid(row=3, column=0, columnspan=2, sticky="ew")
        self.file_frame.columnconfigure(0, weight=1)
        ttk.Entry(self.file_frame, textvariable=self.input_file_var).grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(self.file_frame, text="Browse", command=self.pick_input_file).grid(row=0, column=1)

        self.text_box = tk.Text(self, height=12, wrap="word")
        self.text_box.grid(row=4, column=0, sticky="nsew", pady=10)

        actions = ttk.Frame(self)
        actions.grid(row=5, column=0, sticky="ew")
        ttk.Button(actions, text="Encrypt & Save", command=self.encrypt_and_save).pack(side="left")
        ttk.Button(actions, text="Clear", command=self.clear_form).pack(side="left", padx=6)

        self.result_box = tk.Text(self, height=10, wrap="word")
        self.result_box.grid(row=6, column=0, sticky="nsew", pady=(10, 0))

    def refresh_choices(self):
        self.sender_cb["values"] = self.app.profiles_cache
        self.recipient_cb["values"] = self.app.contacts_cache

        if self.app.profiles_cache and not self.sender_cb.get():
            self.sender_cb.current(0)
        if self.app.contacts_cache and not self.recipient_cb.get():
            self.recipient_cb.current(0)

    def toggle_mode(self):
        mode = self.input_mode.get()
        if mode == "text":
            self.file_frame.grid_remove()
            self.text_box.grid()
        else:
            self.text_box.grid_remove()
            self.file_frame.grid()

    def pick_input_file(self):
        file_path = filedialog.askopenfilename(title="Chọn file input")
        if file_path:
            self.input_file_var.set(file_path)

    def _get_plaintext_bytes(self) -> bytes:
        if self.input_mode.get() == "text":
            text = self.text_box.get("1.0", tk.END).rstrip("\n")
            if not text:
                raise ValueError("Nội dung text đang trống.")
            return text.encode("utf-8")

        file_path = self.input_file_var.get().strip()
        if not file_path:
            raise ValueError("Chưa chọn file input.")
        return Path(file_path).read_bytes()

    def encrypt_and_save(self):
        sender_name = self.sender_cb.get().strip()
        recipient_name = self.recipient_cb.get().strip()

        if not sender_name or not recipient_name:
            messagebox.showwarning("Warning", "Cần chọn sender profile và recipient contact.")
            return

        out_path = filedialog.asksaveasfilename(
            title="Lưu encrypted envelope",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile="message.enc.json",
        )
        if not out_path:
            return

        try:
            sender_profile = self.app.key_service.load_profile(sender_name)
            recipient_contact = self.app.key_service.load_contact(recipient_name)
            plaintext = self._get_plaintext_bytes()

            result = self.app.crypto_service.encrypt_message(
                sender_profile=sender_profile,
                receiver_contact=recipient_contact,
                plaintext=plaintext,
                include_debug=True,
            )

            Path(out_path).write_text(
                json.dumps(result["envelope"], indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

            self.result_box.delete("1.0", tk.END)
            self.result_box.insert(
                "1.0",
                json.dumps(result, indent=2, ensure_ascii=False, default=str),
            )

            self.app.set_status("Encrypt thành công.")
            messagebox.showinfo("Success", f"Đã lưu file:\n{out_path}")
        except Exception as exc:
            messagebox.showerror("Encrypt error", str(exc))
            self.app.set_status("Encrypt thất bại.")

    def clear_form(self):
        self.input_file_var.set("")
        self.text_box.delete("1.0", tk.END)
        self.result_box.delete("1.0", tk.END)