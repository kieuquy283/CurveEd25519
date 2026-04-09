from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


class KeyTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=12)
        self.app = app

        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        ttk.Label(self, text="Key Management", font=("Segoe UI", 14, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 10)
        )

        top = ttk.Frame(self)
        top.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        top.columnconfigure(1, weight=1)

        ttk.Label(top, text="Profile name").grid(row=0, column=0, sticky="w")
        self.profile_name_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.profile_name_var).grid(
            row=0, column=1, sticky="ew", padx=8
        )

        ttk.Button(top, text="Create profile", command=self.create_profile).grid(row=0, column=2)
        ttk.Button(top, text="Refresh", command=self.app.refresh_all).grid(row=0, column=3, padx=6)
        ttk.Button(top, text="Export contact", command=self.export_contact).grid(row=0, column=4)

        mid = ttk.Frame(self)
        mid.grid(row=2, column=0, sticky="nsew")
        mid.columnconfigure(0, weight=1)
        mid.columnconfigure(1, weight=2)
        mid.rowconfigure(0, weight=1)

        self.profile_list = tk.Listbox(mid, exportselection=False)
        self.profile_list.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.profile_list.bind("<<ListboxSelect>>", self.on_select)

        self.details = tk.Text(mid, wrap="word")
        self.details.grid(row=0, column=1, sticky="nsew")

    def refresh_profiles(self):
        self.profile_list.delete(0, tk.END)
        for name in self.app.profiles_cache:
            self.profile_list.insert(tk.END, name)

        self.details.delete("1.0", tk.END)
        self.app.set_status(f"Loaded {len(self.app.profiles_cache)} profiles.")

    def create_profile(self):
        name = self.profile_name_var.get().strip()
        if not name:
            messagebox.showwarning("Warning", "Tên profile không được để trống.")
            return

        try:
            self.app.key_service.create_profile(name)
            self.profile_name_var.set("")
            self.app.refresh_all()
            self.app.set_status("Tạo profile thành công.")
            messagebox.showinfo("Success", f"Đã tạo profile: {name}")
        except Exception as exc:
            messagebox.showerror("Create profile error", str(exc))
            self.app.set_status("Tạo profile thất bại.")

    def export_contact(self):
        sel = self.profile_list.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Hãy chọn một profile.")
            return

        profile_name = self.app.profiles_cache[sel[0]]

        out_path = filedialog.asksaveasfilename(
            title="Export contact",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialfile=f"{profile_name}.contact.json",
        )
        if not out_path:
            return

        try:
            contact = self.app.key_service.export_contact_from_profile(
                profile_name,
                save_to_contacts=False,
            )
            Path(out_path).write_text(
                json.dumps(contact, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            self.app.set_status("Export contact thành công.")
            messagebox.showinfo("Success", f"Đã export contact:\n{out_path}")
        except Exception as exc:
            messagebox.showerror("Export error", str(exc))
            self.app.set_status("Export contact thất bại.")

    def on_select(self, _event=None):
        sel = self.profile_list.curselection()
        if not sel:
            return

        name = self.app.profiles_cache[sel[0]]
        self.details.delete("1.0", tk.END)

        try:
            summary = self.app.key_service.get_profile_summary(name)
            pretty = json.dumps(summary, indent=2, ensure_ascii=False)
        except Exception:
            try:
                full_profile = self.app.key_service.load_profile(name)
                pretty = json.dumps(full_profile, indent=2, ensure_ascii=False)
            except Exception as exc:
                pretty = f"Không tải được profile:\n{exc}"

        self.details.insert("1.0", pretty)