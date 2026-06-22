"""Punto de entrada de la aplicación HymnChords."""

from __future__ import annotations
import tkinter as tk

from database.config import load_config
from database.db import Database
from ui.app import App
from utils.logging_setup import setup_logging
from utils.resources import resource_path


def main() -> None:
    setup_logging()
    config = load_config()
    db = Database(config)
    db.init_schema()
    db.backup("startup")  # respaldo al arrancar (una vez por sesión)

    root = tk.Tk()
    root.title("HymnChords")
    root.geometry("1200x750")
    root.minsize(900, 600)
    try:
        root.iconbitmap(str(resource_path("assets/icon.ico")))
    except tk.TclError:
        pass  # sin ícono no es fatal

    App(root, db)
    root.mainloop()


if __name__ == "__main__":
    main()
