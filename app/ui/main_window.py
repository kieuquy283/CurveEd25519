from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from app.services.key_service import KeyService
from app.services.crypto_service import CryptoService
from app.ui.tabs.contacts_tab import ContactsTab
from app.ui.tabs.decrypt_tab import DecryptTab
from app.ui.tabs.encrypt_tab import EncryptTab
from app.ui.tabs.key_tab import KeyTab
from app.ui.tabs.sign_tab import SignTab


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("CurveApp - X25519 / Ed25519")
        self.geometry("980x720")
        self.minsize(900, 650)

        # services
        self.key_service = KeyService(base_dir="data")
        self.crypto_service = CryptoService

        # caches
        self.profiles_cache: list[str] = []
        self.contacts_cache: list[str] = []

        self._build_ui()
        self.refresh_all()

    def _build_ui(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        container = ttk.Frame(self, padding=8)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=1)
        container.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(container)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        self.key_tab = KeyTab(self.notebook, self)
        self.contacts_tab = ContactsTab(self.notebook, self)
        self.encrypt_tab = EncryptTab(self.notebook, self)
        self.decrypt_tab = DecryptTab(self.notebook, self)
        self.sign_tab = SignTab(self.notebook, self)

        self.notebook.add(self.key_tab, text="Keys")
        self.notebook.add(self.contacts_tab, text="Contacts")
        self.notebook.add(self.encrypt_tab, text="Encrypt")
        self.notebook.add(self.decrypt_tab, text="Decrypt")
        self.notebook.add(self.sign_tab, text="Sign")

        self.status_var = tk.StringVar(value="Ready.")
        status_bar = ttk.Label(container, textvariable=self.status_var, anchor="w")
        status_bar.grid(row=1, column=0, sticky="ew", pady=(6, 0))

    def set_status(self, message: str):
        self.status_var.set(message)

    def refresh_all(self):
        self.profiles_cache = self.key_service.list_profiles()
        self.contacts_cache = self.key_service.list_contacts()

        self.key_tab.refresh_profiles()
        self.contacts_tab.refresh_contacts()
        self.encrypt_tab.refresh_choices()
        self.decrypt_tab.refresh_choices()
        self.sign_tab.refresh_choices()


def run_app():
    app = MainWindow()
    app.mainloop()