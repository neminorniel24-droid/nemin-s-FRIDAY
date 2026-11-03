"""
Find, read and open your files, and use the clipboard.

Safety: she can only look inside your Documents, Downloads and Desktop folders (or the folders in
FILES_ROOTS), never reads secret-looking files, and never opens programs or scripts.
"""
import os
import re
import subprocess
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import config
from . import Result, action
from .winshell import ps_quote, run_ps

TEXT_EXT = {".txt", ".md", ".csv", ".log", ".json", ".yaml", ".yml", ".ini", ".py", ".js", ".ts", ".tsx",
            ".html", ".css", ".c", ".cpp", ".java", ".sh", ".sql", ".xml", ".tex", ".rtf"}
NEVER_OPEN = {".exe", ".bat", ".cmd", ".com", ".msi", ".ps1", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".scr",
              ".lnk", ".jar", ".hta", ".reg", ".dll", ".sh", ".py", ".appx", ".msix", ".url"}
SECRET_NAMES = re.compile(r"(\.env|id_rsa|id_ed25519|\.pem|\.key|\.pfx|token|credential|secret|password|passwd|\.kdbx)", re.I)
SKIP_DIRS = {"node_modules", ".git", "appdata", "__pycache__", ".venv", "venv", "$recycle.bin"}
MAX_READ_BYTES = 5_000_000
STOP = {"the", "a", "an", "my", "file", "document", "doc", "pdf", "please", "find", "open", "read", "of", "called", "named"}

_ROOT_CACHE: list[Path] | None = None


def roots() -> list[Path]:
    """Folders she may look in."""
    global _ROOT_CACHE
    if config.FILES_ROOTS:
        return [Path(p) for p in config.FILES_ROOTS if Path(p).is_dir()]
    if _ROOT_CACHE is not None:
        return _ROOT_CACHE
    found: list[Path] = []
    ok, out = run_ps("[Environment]::GetFolderPath('MyDocuments'); "
                     "(New-Object -ComObject Shell.Application).NameSpace('shell:Downloads').Self.Path; "
                     "[Environment]::GetFolderPath('Desktop')")
    if ok:
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                p = subprocess.run(["wslpath", "-u", line], capture_output=True, text=True, timeout=5).stdout.strip()
            except Exception:
                continue
            if p and Path(p).is_dir():
                found.append(Path(p))
    if found:
        _ROOT_CACHE = found
    return found


def _inside_roots(path: Path) -> bool:
    try:
        real = path.resolve()
    except OSError:
        return False
    return any(real == r.resolve() or r.resolve() in real.parents for r in roots())


def search(query: str, limit: int = 8, max_depth: int = 4) -> list[Path]:
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if w not in STOP]
    if not words:
        return []
    hits: list[tuple[float, Path]] = []
    scanned = 0
    for root in roots():
        base_depth = len(root.parts)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith(".")]
            if len(Path(dirpath).parts) - base_depth >= max_depth:
                dirnames[:] = []
            for fn in filenames:
                scanned += 1
                if scanned > 30000:
                    break
                low = fn.lower()
                if fn.startswith(".") or SECRET_NAMES.search(fn):
                    continue
                if all(w in low for w in words):
                    p = Path(dirpath) / fn
                    try:
                        hits.append((p.stat().st_mtime, p))
                    except OSError:
                        pass
            if scanned > 30000:
                break
    hits.sort(key=lambda t: t[0], reverse=True)
    return [p for _, p in hits[:limit]]


def _resolve(a: dict) -> tuple[Path | None, str]:
    """Pick the file from {"path": ...} (must be inside her folders) or {"query": ...}."""
    raw = str(a.get("path") or "").strip()
    if raw:
        p = Path(raw)
        if p.is_file() and _inside_roots(p) and not SECRET_NAMES.search(p.name):
            return p, ""
        return None, "I can only use files in your Documents, Downloads and Desktop folders."
    q = str(a.get("query") or a.get("name") or "").strip()
    if not q:
        return None, "Which file?"
    found = search(q, 3)
    if not found:
        return None, f"I couldn't find a file matching {q}."
    return found[0], ""


def _docx_text(p: Path) -> str:
    with zipfile.ZipFile(p) as z:
        xml = z.read("word/document.xml")
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    root = ElementTree.fromstring(xml)
    paras = ["".join(t.text or "" for t in para.iter(ns + "t")) for para in root.iter(ns + "p")]
    return "\n".join(x for x in paras if x.strip())


def _pdf_text(p: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("PDF reading needs pypdf. Run: backend/.venv/bin/pip install pypdf")
    reader = PdfReader(str(p))
    return "\n".join((pg.extract_text() or "") for pg in reader.pages[:6])


def read_text(p: Path) -> str:
    ext = p.suffix.lower()
    if p.stat().st_size > MAX_READ_BYTES:
        raise RuntimeError("That file is too big for me to read.")
    if ext in TEXT_EXT:
        return p.read_text(encoding="utf-8", errors="replace")
    if ext == ".docx":
        return _docx_text(p)
    if ext == ".pdf":
        return _pdf_text(p)
    raise RuntimeError(f"I can't read {ext or 'that kind of'} files.")


@action("find_file", "info", 'Find files by name in Documents, Downloads, Desktop. args: {"query": "resume pdf"}')
def find_file(a: dict) -> Result:
    q = str(a.get("query", "")).strip()
    found = search(q, 5)
    if not q:
        return Result(False, "What should I look for?")
    if not found:
        return Result(True, f"I found no files matching {q}.")
    return Result(True, "Found:\n" + "\n".join(f"{p.name} (in {p.parent.name})" for p in found))


@action("read_file", "info",
        'Read a document so you can answer questions or summarise it (txt, md, csv, code, docx, pdf). args: {"query": "report"}')
def read_file(a: dict) -> Result:
    p, err = _resolve(a)
    if not p:
        return Result(False, err)
    try:
        text = read_text(p).strip()
    except Exception as e:  # noqa: BLE001
        return Result(False, str(e)[:160])
    if not text:
        return Result(False, f"{p.name} has no readable text.")
    clipped = text[:6000]
    more = " (cut short)" if len(text) > 6000 else ""
    return Result(True, f"Contents of {p.name}{more}:\n{clipped}")


@action("open_file", "pc", 'Open a document or media file with its normal program. args: {"query": "resume"}')
def open_file(a: dict) -> Result:
    p, err = _resolve(a)
    if not p:
        return Result(False, err)
    if p.suffix.lower() in NEVER_OPEN:
        return Result(False, "I don't open programs or scripts.")
    try:
        win = subprocess.run(["wslpath", "-w", str(p)], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        win = ""
    if not win:
        return Result(False, "I couldn't work out where that file is on Windows.")
    ok, out = run_ps(f"Start-Process -LiteralPath {ps_quote(win)}")
    return Result(True, f"Opening {p.name}.") if ok else Result(False, out)


@action("read_clipboard", "info", "Read what is on the clipboard (what he last copied). args: {}")
def read_clipboard(a: dict) -> Result:
    ok, out = run_ps("Get-Clipboard -Raw")
    if not ok:
        return Result(False, out)
    out = out.strip()
    if not out:
        return Result(True, "The clipboard is empty.")
    return Result(True, "Clipboard contains:\n" + out[:2500] + (" (cut short)" if len(out) > 2500 else ""))


@action("copy_to_clipboard", "pc", 'Put text on the clipboard. args: {"text": "..."}')
def copy_to_clipboard(a: dict) -> Result:
    text = str(a.get("text", ""))[:5000]
    if not text:
        return Result(False, "What should I copy?")
    ok, out = run_ps(f"Set-Clipboard -Value {ps_quote(text)}")
    return Result(True, "Copied to the clipboard.") if ok else Result(False, out)
