from __future__ import annotations

import json
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


class ContactsTab(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, padding=12)
        self.app = app

        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        title = ttk.Label(self, text="Contacts", font=("Segoe UI", 14, "bold"))
        title.grid(row=0, column=0, sticky="w", pady=(0, 10))

        main = ttk.Frame(self)
        main.grid(row=1, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=2)
        main.rowconfigure(0, weight=1)

        left = ttk.Frame(main)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.columnconfigure(0, weight=1)
        left.rowconfigure(1, weight=1)

        btns = ttk.Frame(left)
        btns.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Button(btns, text="Import contact", command=self.import_contact).pack(side="left")
        ttk.Button(btns, text="Refresh", command=self.app.refresh_all).pack(side="left", padx=6)
        ttk.Button(btns, text="Delete", command=self.delete_selected).pack(side="left")

        self.contacts_list = tk.Listbox(left, exportselection=False)
        self.contacts_list.grid(row=1, column=0, sticky="nsew")
        self.contacts_list.bind("<<ListboxSelect>>", self.on_select)

        right = ttk.LabelFrame(main, text="Details", padding=10)
        right.grid(row=0, column=1, sticky="nsew")

        self.details = tk.Text(right, height=20, wrap="word")
        self.details.pack(fill="both", expand=True)

    def refresh_contacts(self):
        self.contacts_list.delete(0, tk.END)
        for name in self.app.contacts_cache:
            self.contacts_list.insert(tk.END, name)

        self.details.delete("1.0", tk.END)
        self.app.set_status(f"Loaded {len(self.app.contacts_cache)} contacts.")

    def on_select(self, _event=None):
        sel = self.contacts_list.curselection()
        if not sel:
            return

        name = self.app.contacts_cache[sel[0]]
        self.details.delete("1.0", tk.END)

        try:
            summary = self.app.key_service.get_contact_summary(name)
            pretty = json.dumps(summary, indent=2, ensure_ascii=False)
        except Exception:
            try:
                contact = self.app.key_service.load_contact(name)
                pretty = json.dumps(contact, indent=2, ensure_ascii=False)
            except Exception as exc:
                pretty = f"Không tải được contact:\n{exc}"

        self.details.insert("1.0", pretty)

    def import_contact(self):
        file_path = filedialog.askopenfilename(
            title="Chọn contact file",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
        )
        if not file_path:
            return

        try:
            self.app.key_service.import_contact_from_file(file_path, save=True)
            self.app.refresh_all()
            self.app.set_status("Import contact thành công.")
            messagebox.showinfo("Success", "Đã import contact.")
        except Exception as exc:
            messagebox.showerror("Import error", str(exc))
            self.app.set_status("Import contact thất bại.")

    def delete_selected(self):
        sel = self.contacts_list.curselection()
        if not sel:
            messagebox.showwarning("Warning", "Hãy chọn một contact.")
            return

        name = self.app.contacts_cache[sel[0]]

        if not messagebox.askyesno("Confirm", f"Xóa contact '{name}'?"):
            return

        try:
            self.app.key_service.delete_contact(name)
            self.app.refresh_all()
            self.app.set_status("Đã xóa contact.")
        except Exception as exc:
            messagebox.showerror("Delete error", str(exc))
            self.app.set_status("Xóa contact thất bại.")