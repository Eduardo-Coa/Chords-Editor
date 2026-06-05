"""Punto de entrada de la aplicación HymnChords."""

from __future__ import annotations
import tkinter as tk

from database.config import load_config
from database.db import Database
from ui.app import App


def main() -> None:
    config = load_config()
    db = Database(config)
    db.init_schema()

    root = tk.Tk()
    root.title("HymnChords")
    root.geometry("1200x750")
    root.minsize(900, 600)

    App(root, db)
    root.mainloop()


if __name__ == "__main__":
    main()
