from __future__ import annotations

import json
import threading
import traceback
from dataclasses import asdict
from pathlib import Path
from tkinter import (
    Tk,
    StringVar,
    BooleanVar,
    IntVar,
    DoubleVar,
    filedialog,
    messagebox,
    Text,
)
from tkinter import ttk

from nc_baxis_constant_surface_speed.core.config import BcssConfig
from nc_baxis_constant_surface_speed.core.processor import process_file


APP_TITLE = "NC B-axis Constant Surface Speed (BCSS)"


def _load_settings(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_settings(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class App:
    def __init__(self, root: Tk) -> None:
        self.root = root
        root.title(APP_TITLE)
        root.geometry("880x560")

        self.settings_path = Path.cwd() / "bcss_settings.json"
        s = _load_settings(self.settings_path)

        # Paths
        self.in_path = StringVar(value=s.get("in_path", ""))
        self.out_dir = StringVar(value=s.get("out_dir", ""))

        # Defaults from your CLI example
        self.tool_d = DoubleVar(value=float(s.get("tool_d", 20.0)))
        # NEW: baseline angle (B-ref). Internally converted if invert-b is ON.
        self.theta_ref = DoubleVar(value=float(s.get("theta_ref", 12.0)))
        self.s_ref = IntVar(value=int(s.get("s_ref", 8000)))

        self.theta_step = DoubleVar(value=float(s.get("theta_step", 1.0)))
        self.theta_min = DoubleVar(value=float(s.get("theta_min", 1.0)))

        self.s_min = IntVar(value=int(s.get("s_min", 1000)))
        self.s_max = IntVar(value=int(s.get("s_max", 20000)))
        self.s_round = IntVar(value=int(s.get("s_round", 10)))
        self.deadband = IntVar(value=int(s.get("deadband", 50)))

        # IMPORTANT: default ON
        self.invert_b = BooleanVar(value=bool(s.get("invert_b", True)))

        self.status = StringVar(value="Ready.")
        self._busy = False

        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        frm = ttk.Frame(self.root)
        frm.pack(fill="both", expand=True, **pad)

        # ---------- File selection ----------
        file_box = ttk.LabelFrame(frm, text="Input / Output")
        file_box.pack(fill="x", **pad)

        row = ttk.Frame(file_box)
        row.pack(fill="x", **pad)
        ttk.Label(row, text="Input EIA").pack(side="left")
        ttk.Entry(row, textvariable=self.in_path, width=95).pack(side="left", padx=8, fill="x", expand=True)
        ttk.Button(row, text="Browse...", command=self._browse_input).pack(side="left")

        row2 = ttk.Frame(file_box)
        row2.pack(fill="x", **pad)
        ttk.Label(row2, text="Output dir (optional)").pack(side="left")
        ttk.Entry(row2, textvariable=self.out_dir, width=95).pack(side="left", padx=8, fill="x", expand=True)
        ttk.Button(row2, text="Browse...", command=self._browse_outdir).pack(side="left")

        # ---------- Settings ----------
        st_box = ttk.LabelFrame(frm, text="Settings")
        st_box.pack(fill="x", **pad)

        grid = ttk.Frame(st_box)
        grid.pack(fill="x", **pad)

        def add_entry(row_i: int, col_i: int, label: str, var, width: int = 12):
            ttk.Label(grid, text=label).grid(row=row_i, column=col_i, sticky="w", padx=6, pady=4)
            ttk.Entry(grid, textvariable=var, width=width).grid(row=row_i, column=col_i + 1, sticky="w", padx=6, pady=4)

        # Row 0
        add_entry(0, 0, "Tool diameter D (mm)  ※(currently not used in Mode A)", self.tool_d)
        add_entry(0, 2, "θ_ref (deg) (B-ref)", self.theta_ref)   # NEW + important
        add_entry(0, 4, "S_ref (rpm)", self.s_ref)

        # Row 1
        add_entry(1, 0, "θ_step (deg) floor", self.theta_step)
        add_entry(1, 2, "θ_min (deg) safety", self.theta_min)
        ttk.Checkbutton(
            grid,
            text="invert-b (θ = 90 - B) [default ON]",
            variable=self.invert_b,
        ).grid(row=1, column=4, columnspan=2, sticky="w", padx=6, pady=4)

        # Row 2
        add_entry(2, 0, "S min (rpm)", self.s_min)
        add_entry(2, 2, "S max (rpm)", self.s_max)
        add_entry(2, 4, "S round unit (rpm)", self.s_round)

        # Row 3
        add_entry(3, 0, "Δrpm deadband (rpm)", self.deadband)

        # ---------- Actions ----------
        act = ttk.Frame(frm)
        act.pack(fill="x", **pad)

        self.btn_run = ttk.Button(act, text="Run (convert)", command=self._run_clicked)
        self.btn_run.pack(side="left")

        ttk.Button(act, text="Save settings", command=self._save_clicked).pack(side="left", padx=8)

        ttk.Label(act, textvariable=self.status).pack(side="left", padx=12)

        # ---------- Log area ----------
        log_box = ttk.LabelFrame(frm, text="Log")
        log_box.pack(fill="both", expand=True, **pad)

        self.log = Text(log_box, height=14)
        self.log.pack(fill="both", expand=True, padx=10, pady=8)
        self._log("Ready.")

    def _log(self, msg: str) -> None:
        self.log.insert("end", msg + "\n")
        self.log.see("end")

    def _browse_input(self) -> None:
        p = filedialog.askopenfilename(
            title="Select input .EIA",
            filetypes=[("EIA files", "*.EIA"), ("All files", "*.*")],
        )
        if p:
            self.in_path.set(p)
            if not self.out_dir.get():
                self.out_dir.set(str(Path(p).parent))

    def _browse_outdir(self) -> None:
        d = filedialog.askdirectory(title="Select output directory")
        if d:
            self.out_dir.set(d)

    def _save_clicked(self) -> None:
        data = {
            "in_path": self.in_path.get(),
            "out_dir": self.out_dir.get(),
            "tool_d": float(self.tool_d.get()),
            "theta_ref": float(self.theta_ref.get()),  # NEW
            "s_ref": int(self.s_ref.get()),
            "theta_step": float(self.theta_step.get()),
            "theta_min": float(self.theta_min.get()),
            "s_min": int(self.s_min.get()),
            "s_max": int(self.s_max.get()),
            "s_round": int(self.s_round.get()),
            "deadband": int(self.deadband.get()),
            "invert_b": bool(self.invert_b.get()),
        }
        try:
            _save_settings(self.settings_path, data)
            self.status.set(f"Saved: {self.settings_path.name}")
            self._log(f"[OK] Saved settings to {self.settings_path}")
        except Exception as e:
            messagebox.showerror("Save error", str(e))

    def _run_clicked(self) -> None:
        if self._busy:
            return

        in_path = self.in_path.get().strip()
        if not in_path:
            messagebox.showwarning("Missing input", "Please select an input .EIA file.")
            return

        inp = Path(in_path)
        if not inp.exists():
            messagebox.showerror("Input not found", f"File not found:\n{inp}")
            return

        out_dir_text = self.out_dir.get().strip()
        out_dir = Path(out_dir_text) if out_dir_text else inp.parent

        # Build config (Mode A)
        cfg = BcssConfig(
            tool_d_mm=float(self.tool_d.get()),
            theta_ref_deg=float(self.theta_ref.get()),  # NEW: user controls baseline angle
            s_ref_rpm=int(self.s_ref.get()),
            theta_step_deg=float(self.theta_step.get()),
            theta_min_deg=float(self.theta_min.get()),
            s_min_rpm=int(self.s_min.get()),
            s_max_rpm=int(self.s_max.get()),
            s_round_unit_rpm=int(self.s_round.get()),
            deadband_rpm=int(self.deadband.get()),
            invert_b_to_theta=bool(self.invert_b.get()),
        )

        # Run in background to keep UI responsive
        self._busy = True
        self.btn_run.config(state="disabled")
        self.status.set("Running...")
        self._log("[RUN] Starting conversion...")
        self._log(f"Input : {inp}")
        self._log(f"OutDir: {out_dir}")
        self._log(f"Config: {asdict(cfg)}")

        th = threading.Thread(target=self._run_worker, args=(inp, out_dir, cfg), daemon=True)
        th.start()

    def _run_worker(self, inp: Path, out_dir: Path, cfg: BcssConfig) -> None:
        try:
            process_file(inp, out_dir, cfg)

            stem = inp.stem
            report_path = out_dir / f"{stem}-bcss.report.json"
            out_path = out_dir / f"{stem}-bcss{inp.suffix}"

            rep = {}
            if report_path.exists():
                rep = json.loads(report_path.read_text(encoding="utf-8"))

            def done_ui() -> None:
                self._log("[OK] Conversion finished.")
                self._log(f"Output: {out_path}")
                self._log(f"Report: {report_path}")
                if rep:
                    ch = rep.get("changes", {})
                    det = rep.get("detect", {})
                    srg = rep.get("s_range", {})
                    self._log(
                        "Stats: "
                        f"lines={det.get('total_lines')} "
                        f"B_lines={det.get('b_lines')} "
                        f"inserted={ch.get('inserted_s_lines')} "
                        f"deadband_skips={ch.get('skipped_deadband')} "
                        f"S_range=({srg.get('s_min')}, {srg.get('s_max')})"
                    )
                self.status.set("Done.")
                self._busy = False
                self.btn_run.config(state="normal")

            self.root.after(0, done_ui)

        except Exception as e:
            tb = traceback.format_exc()

            def err_ui() -> None:
                self._log("[ERROR] Conversion failed.")
                self._log(str(e))
                self._log(tb)
                self.status.set("Error.")
                self._busy = False
                self.btn_run.config(state="normal")
                messagebox.showerror("Error", f"{e}")

            self.root.after(0, err_ui)


def main() -> int:
    root = Tk()
    try:
        style = ttk.Style()
        style.theme_use(style.theme_use())
    except Exception:
        pass

    App(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
