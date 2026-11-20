"""
Minimal Tkinter front-end for the regex scrape demo.

Stdlib only. Wraps crawl() / write_output() from web_scrape_regex.

If your Homebrew Python lacks Tk (`No module named '_tkinter'`), launch with
the system interpreter instead, e.g. `/usr/bin/python3 scrape_gui.py`.
"""

from __future__ import annotations

import json
import threading
from typing import Any

from web_scrape_regex import (
    DEFAULT_URL,
    USER_AGENT,
    crawl,
    pages_from_result,
    write_output,
)

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
except ModuleNotFoundError:  # pragma: no cover - depends on how Python was built
    tk = None  # type: ignore[assignment]
    filedialog = messagebox = ttk = None  # type: ignore[assignment]


def format_result(data: dict) -> str:
    """Human-readable summary for the results pane."""
    if data.get("error"):
        return f"error: {data['error']}\n"

    lines: list[str] = []
    crawl_meta = data.get("crawl")
    pages = pages_from_result(data)
    if crawl_meta and len(pages) > 1:
        lines.append(
            f"crawl: fetched {crawl_meta.get('fetched')} / max {crawl_meta.get('max_pages')}"
        )
        lines.append("")

    for i, page in enumerate(pages):
        if len(pages) > 1:
            lines.append(f"--- page {i + 1}/{len(pages)} ---")
        lines.append(f"source: {page.get('source')}")
        lines.append(f"title: {page.get('title')}")
        lines.append(f"h1: {page.get('h1')}")
        lines.append(f"h2: {', '.join(page.get('h2') or []) or '(none)'}")
        lines.append(f"meta: {page.get('meta_description')}")
        lines.append(f"keywords: {', '.join(page.get('keywords') or []) or '(none)'}")
        lines.append(f"canonical: {page.get('canonical')}")
        lines.append(f"og:title: {page.get('og_title')}")
        lines.append(f"og:url: {page.get('og_url')}")
        lines.append(f"emails: {', '.join(page.get('emails') or []) or '(none)'}")
        lines.append(f"phones: {', '.join(page.get('phones') or []) or '(none)'}")
        images = page.get("images") or []
        lines.append(f"images: {', '.join(images[:15]) or '(none)'}")
        stats = page.get("stats") or {}
        lines.append(
            "stats: "
            f"{stats.get('word_count', 0)} words, "
            f"{stats.get('char_count', 0)} chars, "
            f"{stats.get('link_count', 0)} links, "
            f"{stats.get('image_count', 0)} images, "
            f"{stats.get('phone_count', 0)} phones"
        )
        for kind in ("absolute", "relative", "resolved"):
            links = (page.get("links") or {}).get(kind) or []
            lines.append(f"{kind} links ({len(links)}):")
            for link in links[:15]:
                lines.append(f" - {link}")
        if i < len(pages) - 1:
            lines.append("")
    return "\n".join(lines) + "\n"


def parse_optional_int(raw: str) -> int | None:
    text = raw.strip()
    if not text:
        return None
    return int(text)


def build_crawl_kwargs(
    *,
    url: str,
    offline: bool,
    same_host: bool,
    check_robots: bool,
    delay: str,
    timeout: str,
    max_pages: str,
    max_links: str,
    user_agent: str,
) -> dict[str, Any]:
    """Validate form strings into crawl() kwargs. Raises ValueError on bad input."""
    url = url.strip() or DEFAULT_URL
    try:
        delay_f = float(delay.strip() or "0")
        timeout_f = float(timeout.strip() or "15")
        max_pages_i = int(max_pages.strip() or "1")
        max_links_i = parse_optional_int(max_links)
    except ValueError as exc:
        raise ValueError("delay/timeout/max-pages/max-links must be numbers") from exc

    if delay_f < 0 or timeout_f <= 0:
        raise ValueError("delay must be >= 0 and timeout must be > 0")
    if max_pages_i < 1:
        raise ValueError("max-pages must be >= 1")
    if max_links_i is not None and max_links_i < 0:
        raise ValueError("max-links must be >= 0")

    return {
        "start_url": url,
        "offline": offline,
        "max_pages": max_pages_i,
        "delay": delay_f,
        "timeout": timeout_f,
        "user_agent": (user_agent.strip() or USER_AGENT),
        "check_robots": check_robots and not offline,
        "max_links": max_links_i,
        "same_host_only": same_host,
    }


if tk is not None:

    class ScrapeApp(ttk.Frame):
        def __init__(self, master: tk.Tk) -> None:
            super().__init__(master, padding=12)
            self.master.title("Regex scrape demo")
            self.master.minsize(720, 520)
            self.pack(fill=tk.BOTH, expand=True)

            self._result: dict | None = None
            self._busy = False

            self.url = tk.StringVar(value=DEFAULT_URL)
            self.offline = tk.BooleanVar(value=True)
            self.same_host = tk.BooleanVar(value=False)
            self.check_robots = tk.BooleanVar(value=False)
            self.delay = tk.StringVar(value="0")
            self.timeout = tk.StringVar(value="15")
            self.max_pages = tk.StringVar(value="1")
            self.max_links = tk.StringVar(value="")
            self.user_agent = tk.StringVar(value=USER_AGENT)
            self.show_json = tk.BooleanVar(value=False)
            self.status = tk.StringVar(value="Ready (offline sample by default)")

            self._build()

        def _build(self) -> None:
            form = ttk.LabelFrame(self, text="Options", padding=10)
            form.pack(fill=tk.X)

            ttk.Label(form, text="URL").grid(row=0, column=0, sticky=tk.W, pady=2)
            ttk.Entry(form, textvariable=self.url, width=64).grid(
                row=0, column=1, columnspan=5, sticky=tk.EW, pady=2, padx=(8, 0)
            )

            ttk.Checkbutton(form, text="Offline sample", variable=self.offline).grid(
                row=1, column=1, sticky=tk.W, pady=2
            )
            ttk.Checkbutton(form, text="Same host", variable=self.same_host).grid(
                row=1, column=2, sticky=tk.W, pady=2
            )
            ttk.Checkbutton(form, text="Check robots.txt", variable=self.check_robots).grid(
                row=1, column=3, sticky=tk.W, pady=2
            )
            ttk.Checkbutton(form, text="Show JSON", variable=self.show_json).grid(
                row=1, column=4, sticky=tk.W, pady=2
            )

            ttk.Label(form, text="Delay").grid(row=2, column=0, sticky=tk.W, pady=2)
            ttk.Entry(form, textvariable=self.delay, width=8).grid(
                row=2, column=1, sticky=tk.W, padx=(8, 0), pady=2
            )
            ttk.Label(form, text="Timeout").grid(row=2, column=2, sticky=tk.W, pady=2)
            ttk.Entry(form, textvariable=self.timeout, width=8).grid(
                row=2, column=3, sticky=tk.W, padx=(8, 0), pady=2
            )
            ttk.Label(form, text="Max pages").grid(row=3, column=0, sticky=tk.W, pady=2)
            ttk.Entry(form, textvariable=self.max_pages, width=8).grid(
                row=3, column=1, sticky=tk.W, padx=(8, 0), pady=2
            )
            ttk.Label(form, text="Max links").grid(row=3, column=2, sticky=tk.W, pady=2)
            ttk.Entry(form, textvariable=self.max_links, width=8).grid(
                row=3, column=3, sticky=tk.W, padx=(8, 0), pady=2
            )

            ttk.Label(form, text="User-Agent").grid(row=4, column=0, sticky=tk.W, pady=2)
            ttk.Entry(form, textvariable=self.user_agent, width=64).grid(
                row=4, column=1, columnspan=5, sticky=tk.EW, padx=(8, 0), pady=2
            )

            form.columnconfigure(1, weight=1)
            form.columnconfigure(5, weight=1)

            actions = ttk.Frame(self)
            actions.pack(fill=tk.X, pady=(10, 6))
            self.run_btn = ttk.Button(actions, text="Run", command=self.on_run)
            self.run_btn.pack(side=tk.LEFT)
            ttk.Button(actions, text="Clear", command=self.on_clear).pack(
                side=tk.LEFT, padx=(8, 0)
            )
            ttk.Button(actions, text="Save…", command=self.on_save).pack(
                side=tk.LEFT, padx=(8, 0)
            )

            out = ttk.LabelFrame(self, text="Results", padding=8)
            out.pack(fill=tk.BOTH, expand=True)
            self.text = tk.Text(out, wrap=tk.WORD, height=22, font=("Menlo", 11))
            scroll = ttk.Scrollbar(out, orient=tk.VERTICAL, command=self.text.yview)
            self.text.configure(yscrollcommand=scroll.set)
            self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            scroll.pack(side=tk.RIGHT, fill=tk.Y)

            ttk.Label(self, textvariable=self.status).pack(anchor=tk.W, pady=(8, 0))

        def _set_busy(self, busy: bool) -> None:
            self._busy = busy
            self.run_btn.configure(state=tk.DISABLED if busy else tk.NORMAL)

        def _set_output(self, text: str) -> None:
            self.text.delete("1.0", tk.END)
            self.text.insert(tk.END, text)

        def on_clear(self) -> None:
            self._result = None
            self._set_output("")
            self.status.set("Cleared")

        def on_run(self) -> None:
            if self._busy:
                return
            try:
                kwargs = build_crawl_kwargs(
                    url=self.url.get(),
                    offline=self.offline.get(),
                    same_host=self.same_host.get(),
                    check_robots=self.check_robots.get(),
                    delay=self.delay.get(),
                    timeout=self.timeout.get(),
                    max_pages=self.max_pages.get(),
                    max_links=self.max_links.get(),
                    user_agent=self.user_agent.get(),
                )
            except ValueError as exc:
                messagebox.showerror("Invalid options", str(exc))
                return

            self._set_busy(True)
            self.status.set("Running…")

            def work() -> None:
                try:
                    data = crawl(**kwargs)
                except Exception as exc:  # noqa: BLE001 — surface any scrape failure in UI
                    self.master.after(0, lambda: self._on_fail(str(exc)))
                    return
                self.master.after(0, lambda: self._on_done(data))

            threading.Thread(target=work, daemon=True).start()

        def _on_fail(self, message: str) -> None:
            self._set_busy(False)
            self.status.set("Failed")
            messagebox.showerror("Scrape failed", message)

        def _on_done(self, data: dict) -> None:
            self._set_busy(False)
            if data.get("error"):
                self._result = data
                self._set_output(format_result(data))
                self.status.set("Blocked / error")
                return

            self._result = data
            if self.show_json.get():
                self._set_output(json.dumps(data, indent=2) + "\n")
            else:
                self._set_output(format_result(data))

            pages = pages_from_result(data)
            self.status.set(f"Done — {len(pages)} page(s)")

        def on_save(self) -> None:
            if not self._result or self._result.get("error"):
                messagebox.showinfo("Nothing to save", "Run a successful scrape first.")
                return
            path = filedialog.asksaveasfilename(
                title="Save scrape result",
                defaultextension=".json",
                filetypes=[
                    ("JSON", "*.json"),
                    ("CSV", "*.csv"),
                    ("Markdown", "*.md"),
                    ("All files", "*.*"),
                ],
            )
            if not path:
                return
            try:
                write_output(path, self._result)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Save failed", str(exc))
                return
            self.status.set(f"Wrote {path}")


def main() -> None:
    if tk is None:
        raise SystemExit(
            "Tkinter is not available in this Python.\n"
            "On macOS try: /usr/bin/python3 scrape_gui.py\n"
            "Or install a Python build with Tk support (e.g. python-tk / official installer)."
        )

    root = tk.Tk()
    try:
        style = ttk.Style(root)
        if "aqua" in style.theme_names():
            style.theme_use("aqua")
        elif "clam" in style.theme_names():
            style.theme_use("clam")
    except tk.TclError:
        pass
    ScrapeApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
