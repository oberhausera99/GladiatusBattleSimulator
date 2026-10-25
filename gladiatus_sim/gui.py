"""Grafikus felület (Tkinter): játékosnév + szerver -> statok -> szimuláció."""
from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk

from . import gui_logic as gl
from .fetch import FetchError
from .turma import TurmaRules


class App(ttk.Frame):
    def __init__(self, root: tk.Tk):
        super().__init__(root, padding=8)
        root.title("Gladiatus szimulátor")
        root.geometry("1160x880")
        root.minsize(900, 700)
        self.grid(sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)
        self.q: "queue.Queue" = queue.Queue()
        self.mode = None            # mode of the downloaded data
        self.team_a = self.team_d = None   # lists (turma) or Fighters (arena)
        self._build_inputs()
        self._build_stats()
        self._build_result()
        self.after(100, self._poll)

    # ---- input row -----------------------------------------------------
    def _build_inputs(self):
        f = ttk.LabelFrame(self, text="Beállítások", padding=6)
        f.grid(row=0, column=0, sticky="ew")
        self.v_mode = tk.StringVar(value="turma")
        ttk.Radiobutton(f, text="Circus Turma (5v5)", variable=self.v_mode, value="turma").grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(f, text="Aréna (1v1)", variable=self.v_mode, value="arena").grid(row=1, column=0, sticky="w")
        ttk.Radiobutton(f, text="Egyesületi csata", variable=self.v_mode, value="guild",
                        command=self._mode_changed).grid(row=2, column=0, sticky="w")
        ttk.Radiobutton(f, text="Legjobb játékos", variable=self.v_mode, value="best",
                        command=self._mode_changed).grid(row=3, column=0, sticky="w")
        for rb in f.grid_slaves(column=0):
            if isinstance(rb, ttk.Radiobutton) and rb.cget("value") not in ("guild", "best"):
                rb.configure(command=self._mode_changed)
        self.settings = f
        self.v_att, self.v_att_srv = tk.StringVar(), tk.StringVar(value="s51-en")
        self.v_def, self.v_def_srv = tk.StringVar(), tk.StringVar(value="s51-en")
        self.lbl_names = []
        self.name_widgets = []
        for r, (lab, vn, vs) in enumerate((("Támadó", self.v_att, self.v_att_srv), ("Védő", self.v_def, self.v_def_srv))):
            lbl = ttk.Label(f, text=f"{lab} neve:")
            lbl.grid(row=r, column=1, padx=(14, 2), sticky="e")
            self.lbl_names.append((lbl, lab))
            e1 = ttk.Entry(f, textvariable=vn, width=22)
            e1.grid(row=r, column=2)
            l2 = ttk.Label(f, text="szerver:")
            l2.grid(row=r, column=3, padx=(8, 2), sticky="e")
            e2 = ttk.Entry(f, textvariable=vs, width=9)
            e2.grid(row=r, column=4)
            self.name_widgets.extend([lbl, e1, l2, e2])
        ttk.Label(f, text="Szimulációk száma:").grid(row=0, column=5, padx=(14, 2), sticky="e")
        self.v_runs = tk.StringVar(value="1000")
        ttk.Spinbox(f, from_=10, to=100000, increment=100, textvariable=self.v_runs, width=8).grid(row=0, column=6)
        self.btn_get = ttk.Button(f, text="Get stats", command=self.get_stats)
        self.btn_get.grid(row=1, column=5, columnspan=2, sticky="ew", padx=(14, 0))
        self.v_full_life = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Egyesületi csata: teljes életerővel számol (alapból az aktuális)",
                        variable=self.v_full_life).grid(row=3, column=1, columnspan=5, sticky="w", padx=(14, 0))
        self.v_debug = tk.BooleanVar(value=False)
        ttk.Checkbutton(f, text="Letöltött lapok mentése (debug_pages mappába)",
                        variable=self.v_debug).grid(row=2, column=1, columnspan=5, sticky="w", padx=(14, 0))
        # "Legjobb játékos" mode
        bf = ttk.Frame(f)
        self.best_frame = bf
        self.v_best = {k: tk.StringVar(value=v) for k, v in
                       (("lo", "130"), ("hi", "150"), ("servers", ""), ("samples", "2"))}
        for i, (lab, key, w) in enumerate((("Szint tól:", "lo", 5), ("ig:", "hi", 5),
                                           ("Szerverek (üres = az összes EN):", "servers", 10),
                                           ("Csata / páros:", "samples", 4))):
            ttk.Label(bf, text=lab).grid(row=0, column=2 * i, padx=(8, 2), sticky="e")
            ttk.Entry(bf, textvariable=self.v_best[key], width=w).grid(row=0, column=2 * i + 1)
        bf.grid(row=4, column=1, columnspan=6, sticky="w", pady=(6, 0))
        bf.grid_remove()
        self.v_status = tk.StringVar(value="Add meg a két játékost, majd kattints a Get stats gombra.")
        ttk.Label(self, textvariable=self.v_status, foreground="#555").grid(row=1, column=0, sticky="w", pady=(4, 4))

    def _mode_changed(self):
        mode = self.v_mode.get()
        for w in self.name_widgets + [lbl for lbl, _ in self.lbl_names]:
            (w.grid_remove if mode == "best" else w.grid)()
        (self.best_frame.grid if mode == "best" else self.best_frame.grid_remove)()
        self.v_status.set("Add meg a szintintervallumot és a szervereket, majd kattints a Get stats gombra."
                          if mode == "best" else "Add meg a két játékost, majd kattints a Get stats gombra.")
        guild = mode == "guild"
        for lbl, lab in self.lbl_names:
            lbl.configure(text=f"{lab} egyesület teljes neve (vagy azonosítója):" if guild else f"{lab} neve:")
        self.v_runs.set("1" if guild else ("10000" if self.v_mode.get() == "arena" else "1000"))

    # ---- stats area ----------------------------------------------------
    def _build_stats(self):
        f = ttk.Frame(self)
        f.grid(row=2, column=0, sticky="nsew")
        f.columnconfigure(1, weight=1)
        f.rowconfigure(0, weight=1)
        self.lists = {}
        for col, side, title in ((0, "a", "Támadó csapat"), (2, "d", "Védő csapat")):
            box = ttk.LabelFrame(f, text=title, padding=4)
            box.grid(row=0, column=col, sticky="ns")
            lb = tk.Listbox(box, width=26, height=6, exportselection=False, activestyle="none")
            lb.grid(row=0, column=0, sticky="ns")
            lb.bind("<<ListboxSelect>>", lambda e: self._refresh_table())
            v = tk.StringVar()
            cb = ttk.Combobox(box, textvariable=v, state="readonly", width=16,
                              values=[gl.ROLE_LABELS[r] for r in ("tank", "dps", "healer", "out")])
            cb.grid(row=2, column=0, pady=(6, 0), sticky="w")
            ttk.Label(box, text="Szerep:").grid(row=1, column=0, sticky="w", pady=(6, 0))
            cb.bind("<<ComboboxSelected>>", lambda e, s=side: self._role_changed(s))
            self.lists[side] = (lb, v, cb)
        mid = ttk.Frame(f)
        mid.grid(row=0, column=1, sticky="nsew", padx=6)
        mid.columnconfigure(0, weight=1)
        mid.rowconfigure(0, weight=1)
        self.table = ttk.Treeview(mid, columns=("a", "l", "d"), show="headings", height=19)
        for c, t, w, an in (("a", "Támadó", 170, "e"), ("l", "", 130, "center"), ("d", "Védő", 170, "w")):
            self.table.heading(c, text=t)
            self.table.column(c, width=w, anchor=an)
        self.table.grid(row=0, column=0, sticky="nsew")
        self.btn_sim = ttk.Button(mid, text="Simulate battle", command=self.simulate, state="disabled")
        self.btn_sim.grid(row=1, column=0, sticky="ew", pady=(6, 0))

    def _build_result(self):
        f = ttk.LabelFrame(self, text="Eredmény", padding=4)
        f.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        f.columnconfigure(0, weight=1)
        self.txt = tk.Text(f, height=11, font=("Courier", 10), wrap="none")
        self.txt.grid(row=0, column=0, sticky="ew")
        self.txt.configure(state="disabled")

    # ---- actions -------------------------------------------------------
    def _busy(self, on: bool, msg: str = ""):
        self.btn_get.configure(state="disabled" if on else "normal")
        self.btn_sim.configure(state="disabled" if on or self.mode is None else "normal")
        if msg:
            self.v_status.set(msg)

    def _run_thread(self, fn, done):
        def work():
            try:
                self.q.put((done, fn(), None))
            except Exception as e:      # shown in the status bar
                self.q.put((done, None, e))
        threading.Thread(target=work, daemon=True).start()

    def _poll(self):
        try:
            while True:
                done, res, err = self.q.get_nowait()
                done(res, err)
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def get_stats(self):
        mode = self.v_mode.get()
        if mode == "best":
            return self._get_best()
        att, dfd = (self.v_att.get(), self.v_att_srv.get()), (self.v_def.get(), self.v_def_srv.get())
        if not att[0].strip() or not dfd[0].strip():
            self.v_status.set("Mindkét játékos nevét add meg.")
            return
        self._busy(True, "Statok letöltése...")
        debug = self.v_debug.get()

        def progress(msg):
            self.q.put((lambda r, e, m=msg: self.v_status.set(m), None, None))

        self._run_thread(lambda: gl.fetch_players(mode, att, dfd, progress=progress,
                                                      debug_dir="debug_pages" if debug else None),
                         lambda r, e: self._got_stats(mode, r, e))

    def _int(self, key: str) -> int:
        try:
            return int(self.v_best[key].get())
        except ValueError:
            raise ValueError(f"Egész számot adj meg ({key})")

    def _get_best(self):
        try:
            lo, hi = self._int("lo"), self._int("hi")
        except ValueError as e:
            self.v_status.set(str(e))
            return
        servers = self.v_best["servers"].get()
        self._busy(True, "Játékosok keresése a toplistákon...")

        def progress(msg):
            self.q.put((lambda r, e, m=msg: self.v_status.set(m), None, None))

        def work():
            b = gl.fetch_best_set(lo, hi, servers, progress=progress)
            return b, b

        self._run_thread(work, lambda r, e: self._got_stats("best", r, e))

    def _got_stats(self, mode, res, err):
        if err is not None:
            self.mode = None
            msg = f"Hiba: {err}" if isinstance(err, (FetchError, ValueError)) else f"Váratlan hiba: {err!r}"
            self._busy(False, msg)
            return
        self.mode = mode
        self.team_a, self.team_d = res
        for side in "ad":
            lb = self.lists[side][0]
            lb.delete(0, "end")
            members = self._members(side)
            for f in members:
                lb.insert("end", self._label(f))
            lb.selection_set(0)
            self.lists[side][2].configure(state="readonly" if mode == "turma" else "disabled")
            self.lists[side][0].configure(height=14 if mode == "guild" else 6)
        self._on_select_sync()
        self._refresh_table()
        if mode == "guild":
            self._busy(False, gl.guild_summary(self.team_a, self.team_d))
            return
        if mode == "best":
            b = self.team_a
            self._busy(False, f"{len(b.fighters)} játékos letöltve ({b.servers} szerver, "
                              f"{len(b.server_errors)} hibás). Kattints a Simulate battle gombra.")
            return
        self._busy(False, "Statok letöltve. Állítsd be a szerepeket, majd kattints a Simulate battle gombra."
                   if mode == "turma" else "Statok letöltve. Kattints a Simulate battle gombra.")

    def _members(self, side):
        t = self.team_a if side == "a" else self.team_d
        if self.mode in ("guild", "best"):
            return t.fighters
        return t if self.mode == "turma" else [t]

    def _label(self, f):
        if self.mode in ("guild", "best"):
            return f"{f.name[:26]:26s} L{f.level}"
        star = "★ " if f.is_main else "   "
        return f"{star}{f.name.split('@')[0][:16]:16s} L{f.level} [{gl.ROLE_LABELS[f.role]}]"

    def _selected(self, side):
        lb = self.lists[side][0]
        sel = lb.curselection()
        members = self._members(side)
        return members[sel[0]] if sel else members[0]

    def _on_select_sync(self):
        for side in "ad":
            self.lists[side][1].set(gl.ROLE_LABELS[self._selected(side).role])

    def _role_changed(self, side):
        f = self._selected(side)
        f.role = gl.ROLE_FROM_LABEL[self.lists[side][1].get()]
        lb = self.lists[side][0]
        i = lb.curselection()[0]
        lb.delete(i)
        lb.insert(i, self._label(f))
        lb.selection_set(i)
        self._refresh_table()

    def _refresh_table(self):
        if self.mode is None:
            return
        self._on_select_sync()
        a, d = self._selected("a"), self._selected("d")
        for row in self.table.get_children():
            self.table.delete(row)
        for lab, va, vd in gl.stat_rows(a, d):
            if self.mode != "turma" and lab in ("Gyógyítás", "Dupla gyógyítás", "Veszély"):
                continue
            self.table.insert("", "end", values=(va, lab, vd))
        if self.mode == "turma":
            self.table.insert("", "end", values=(gl.ROLE_LABELS[a.role], "Szerep", gl.ROLE_LABELS[d.role]))

    def _show(self, text):
        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", text)
        self.txt.configure(state="disabled")

    def simulate(self):
        if self.mode == "best":
            try:
                samples = max(1, self._int("samples"))
            except ValueError as e:
                self.v_status.set(str(e))
                return
            self._busy(True, "Verseny fut...")
            b = self.team_a

            def progress(msg):
                self.q.put((lambda r, e, m=msg: self.v_status.set(m), None, None))

            self._run_thread(lambda: gl.best_text(b, samples, progress=progress), self._sim_done)
            return
        try:
            runs = max(1, int(self.v_runs.get()))
        except ValueError:
            self.v_status.set("A szimulációk száma egész szám legyen.")
            return
        self._busy(True, f"Szimuláció fut ({runs} csata)...")
        mode, a, d = self.mode, self.team_a, self.team_d
        life_mode = "full" if self.v_full_life.get() else "current"
        self._run_thread(lambda: gl.run_simulation(mode, a, d, runs, TurmaRules(), life_mode=life_mode),
                         self._sim_done)

    def _sim_done(self, text, err):
        if err is not None:
            self._busy(False, f"Hiba a szimuláció közben: {err!r}")
            return
        self._show(text)
        self._busy(False, "Kész.")


def main() -> int:
    root = tk.Tk()
    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
