"""Extract plain text from documents: Markdown/text, HTML, DOCX and PDF (stdlib only).

PDF strategy: use `pdftotext` (poppler) or `pypdf` when available; otherwise a built-in parser
that decodes FlateDecode content streams and maps glyph codes to Unicode through each font's
/ToUnicode CMap (the layout produced by Google Docs, Word, Chrome and most generators).
The built-in parser targets text recovery for auditing, not perfect reading order.
"""

import html
import re
import shutil
import subprocess
import unicodedata
import zipfile
import zlib
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def extract_text(path: Path) -> Tuple[str, str]:
    """Return (text, method)."""
    suffix = path.suffix.lower()
    if suffix in {".md", ".txt", ".rst", ".markdown"}:
        return path.read_text(encoding="utf-8", errors="ignore"), "text"
    if suffix in {".html", ".htm"}:
        raw = path.read_text(encoding="utf-8", errors="ignore")
        raw = re.sub(r"<(script|style)[\s\S]*?</\1>", " ", raw, flags=re.I)
        return html.unescape(re.sub(r"<[^>]+>", " ", raw)), "html"
    if suffix == ".docx":
        with zipfile.ZipFile(path) as z:
            xml = z.read("word/document.xml").decode("utf-8", errors="ignore")
        xml = re.sub(r"</w:p>", "\n", xml)
        return html.unescape(re.sub(r"<[^>]+>", "", xml)), "docx"
    if suffix == ".pdf":
        return pdf_text(path)
    raise ValueError(f"unsupported document type: {path.suffix}")


def pdf_text(path: Path) -> Tuple[str, str]:
    if shutil.which("pdftotext"):
        out = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True, timeout=120)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout, "pdftotext"
    try:
        import pypdf  # type: ignore
        reader = pypdf.PdfReader(str(path))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if text.strip():
            return text, "pypdf"
    except Exception:
        pass
    return BuiltinPdf(path.read_bytes()).text(), "builtin"


# ------------------------------------------------------------------------------
# Built-in PDF parser
# ------------------------------------------------------------------------------

OBJ = re.compile(rb"(\d+)\s+(\d+)\s+obj\b(.*?)\bendobj", re.S)
REF = re.compile(rb"(\d+)\s+\d+\s+R")


class BuiltinPdf:
    def __init__(self, data: bytes):
        self.objects: Dict[int, bytes] = {}
        for m in OBJ.finditer(data):
            self.objects[int(m.group(1))] = m.group(3)
        self._expand_object_streams()
        self._cmaps: Dict[int, Tuple[Dict[bytes, str], int]] = {}

    # -- object access ---------------------------------------------------------
    def stream(self, num: int) -> Optional[bytes]:
        body = self.objects.get(num)
        if body is None or b"stream" not in body:
            return None
        head, _, rest = body.partition(b"stream")
        rest = rest[2:] if rest.startswith(b"\r\n") else rest[1:] if rest[:1] in (b"\n", b"\r") else rest
        raw = rest.rsplit(b"endstream", 1)[0]
        length = re.search(rb"/Length\s+(\d+)(?!\s+\d+\s+R)", head)
        if length and int(length.group(1)) <= len(raw):
            raw = raw[: int(length.group(1))]
        if b"/FlateDecode" in head:
            try:
                return zlib.decompress(raw)
            except zlib.error:
                try:
                    return zlib.decompressobj().decompress(raw)
                except zlib.error:
                    return None
        return raw

    def _expand_object_streams(self):
        for num, body in list(self.objects.items()):
            if b"/ObjStm" not in body:
                continue
            data = self.stream(num)
            first = re.search(rb"/First\s+(\d+)", body)
            if not data or not first:
                continue
            offset = int(first.group(1))
            header = data[:offset].split()
            pairs = [(int(header[i]), int(header[i + 1])) for i in range(0, len(header) - 1, 2)]
            for i, (obj_num, start) in enumerate(pairs):
                end = pairs[i + 1][1] if i + 1 < len(pairs) else len(data) - offset
                self.objects.setdefault(obj_num, data[offset + start: offset + end])

    def resolve_dict(self, body: bytes, key: bytes) -> bytes:
        """Return the dictionary text for /key (balanced << >>), following one indirect reference."""
        m = re.search(rb"/" + key + rb"(?![\w])\s*", body)
        if not m:
            return b""
        rest = body[m.end():]
        ref = REF.match(rest)
        if ref:
            return self.objects.get(int(ref.group(1)), b"")
        if not rest.startswith(b"<<"):
            return b""
        depth, i = 0, 0
        while i < len(rest) - 1:
            pair = rest[i:i + 2]
            if pair == b"<<":
                depth += 1
                i += 2
                continue
            if pair == b">>":
                depth -= 1
                i += 2
                if depth == 0:
                    return rest[:i]
                continue
            i += 1
        return rest

    # -- fonts -----------------------------------------------------------------
    def cmap(self, font_num: int) -> Tuple[Dict[bytes, str], int]:
        if font_num in self._cmaps:
            return self._cmaps[font_num]
        body = self.objects.get(font_num, b"")
        mapping: Dict[bytes, str] = {}
        width = 1
        ref = re.search(rb"/ToUnicode\s+(\d+)\s+\d+\s+R", body)
        data = self.stream(int(ref.group(1))) if ref else None
        if data:
            space = re.search(rb"begincodespacerange\s*<([0-9A-Fa-f]+)>", data)
            width = len(space.group(1)) // 2 if space else 2
            for block in re.findall(rb"beginbfchar(.*?)endbfchar", data, re.S):
                for src, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", block):
                    mapping[bytes.fromhex(src.decode())] = _utf16(dst)
            for block in re.findall(rb"beginbfrange(.*?)endbfrange", data, re.S):
                for lo, hi, dst in re.findall(rb"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*(<[0-9A-Fa-f]+>|\[[^\]]*\])", block):
                    lo_i, hi_i, n = int(lo, 16), int(hi, 16), len(lo) // 2
                    if dst.startswith(b"["):
                        for k, item in enumerate(re.findall(rb"<([0-9A-Fa-f]+)>", dst)):
                            mapping[(lo_i + k).to_bytes(n, "big")] = _utf16(item)
                    else:
                        base = int(dst[1:-1], 16)
                        size = len(dst[1:-1]) // 4 or 1
                        for k in range(hi_i - lo_i + 1):
                            mapping[(lo_i + k).to_bytes(n, "big")] = _utf16(format(base + k, f"0{4 * size}X").encode())
        self._cmaps[font_num] = (mapping, width)
        return mapping, width

    def decode(self, raw: bytes, font_num: Optional[int]) -> str:
        if font_num is None:
            return raw.decode("latin-1")
        mapping, width = self.cmap(font_num)
        if not mapping:
            return raw.decode("latin-1")
        out = []
        for i in range(0, len(raw) - width + 1, width):
            out.append(mapping.get(raw[i:i + width], ""))
        return "".join(out)

    # -- pages -----------------------------------------------------------------
    def pages(self) -> List[int]:
        nums = [n for n, b in self.objects.items() if re.search(rb"/Type\s*/Page(?!s)", b)]
        return sorted(nums)

    def text(self) -> str:
        chunks = []
        for page in self.pages():
            body = self.objects[page]
            resources = self.resolve_dict(body, b"Resources")
            fonts_dict = self.resolve_dict(resources, b"Font")
            fonts = {name: int(num) for name, num in re.findall(rb"/([\w.+-]+)\s+(\d+)\s+\d+\s+R", fonts_dict)}
            contents = re.search(rb"/Contents\s*(\[[^\]]*\]|\d+\s+\d+\s+R)", body)
            refs = [int(r) for r in REF.findall(contents.group(1))] if contents else []
            content = b"\n".join(filter(None, (self.stream(r) for r in refs)))
            chunks.append(self._content_text(content, fonts))
        return "\n\n".join(chunks)

    def _content_text(self, content: bytes, fonts: Dict[bytes, int]) -> str:
        out: List[str] = []
        font = None
        last_y = None
        operands: List[object] = []
        for token in _tokens(content):
            kind, value = token
            if kind == "op":
                if value == b"Tf" and len(operands) >= 2 and operands[-2][0] == "name":
                    font = fonts.get(operands[-2][1][1:])
                elif value in (b"Tj", b"'", b'"') and operands and operands[-1][0] == "str":
                    out.append(self.decode(operands[-1][1], font))
                elif value == b"TJ" and operands and operands[-1][0] == "arr":
                    for item in operands[-1][1]:
                        if isinstance(item, tuple) and item[0] == "str":
                            out.append(self.decode(item[1], font))
                        elif isinstance(item, float) and item < -200:
                            out.append(" ")
                elif value in (b"Td", b"TD") and len(operands) >= 2 and operands[-1][0] == "num":
                    # Glyph-by-glyph positioning is common; only a vertical move starts a new line.
                    dy = operands[-1][1]
                    out.append("\n" if abs(dy) > 2 else (" " if abs(operands[-2][1]) > 30 else ""))
                elif value == b"Tm" and len(operands) >= 6 and operands[-1][0] == "num":
                    y = operands[-1][1]
                    out.append("\n" if last_y is None or abs(y - last_y) > 2 else "")
                    last_y = y
                elif value == b"T*":
                    out.append("\n")
                elif value == b"ET":
                    out.append("\n")
                operands = []
            else:
                operands.append(token)
        # NFKC folds Arabic presentation forms (U+FBxx-FExx) back to ordinary letters.
        text = unicodedata.normalize("NFKC", "".join(out))
        return re.sub(r"[ \t]+\n", "\n", re.sub(r"\n{3,}", "\n\n", text))


def _utf16(hex_bytes: bytes) -> str:
    try:
        return bytes.fromhex(hex_bytes.decode()).decode("utf-16-be")
    except (ValueError, UnicodeDecodeError):
        return ""


def _tokens(data: bytes):
    """Minimal content-stream tokenizer: strings, hex strings, arrays, names, numbers, operators."""
    i, n = 0, len(data)
    stack: List[list] = []

    def emit(token):
        if stack:
            stack[-1].append(token[1] if token[0] == "num" else token)
            return None
        return token

    while i < n:
        c = data[i:i + 1]
        if c in b" \t\r\n\f\x00":
            i += 1
        elif c == b"%":
            j = data.find(b"\n", i)
            i = n if j == -1 else j
        elif c == b"(":
            depth, j, buf = 1, i + 1, bytearray()
            while j < n and depth:
                ch = data[j:j + 1]
                if ch == b"\\" and j + 1 < n:
                    nxt = data[j + 1:j + 2]
                    escapes = {b"n": b"\n", b"r": b"\r", b"t": b"\t", b"b": b"\b", b"f": b"\f"}
                    if nxt in escapes:
                        buf += escapes[nxt]; j += 2
                    elif nxt.isdigit():
                        octal = re.match(rb"[0-7]{1,3}", data[j + 1:j + 4]).group(0)
                        buf.append(int(octal, 8) & 0xFF); j += 1 + len(octal)
                    else:
                        buf += nxt; j += 2
                    continue
                if ch == b"(":
                    depth += 1
                elif ch == b")":
                    depth -= 1
                    if depth == 0:
                        break
                buf += ch
                j += 1
            tok = emit(("str", bytes(buf)))
            if tok:
                yield tok
            i = j + 1
        elif c == b"<" and data[i:i + 2] != b"<<":
            j = data.find(b">", i)
            hexstr = re.sub(rb"\s", b"", data[i + 1:j])
            if len(hexstr) % 2:
                hexstr += b"0"
            tok = emit(("str", bytes.fromhex(hexstr.decode() or "")))
            if tok:
                yield tok
            i = j + 1
        elif c == b"[":
            stack.append([])
            i += 1
        elif c == b"]":
            arr = stack.pop() if stack else []
            tok = emit(("arr", arr))
            if tok:
                yield ("arr", arr)
            i += 1
        elif data[i:i + 2] in (b"<<", b">>"):
            i += 2
        else:
            m = re.match(rb"/[^\s/\[\]()<>{}%]*|[+-]?(?:\d+\.?\d*|\.\d+)|[^\s/\[\]()<>{}%]+", data[i:])
            word = m.group(0) if m else data[i:i + 1]
            i += max(1, len(word))
            if word.startswith(b"/"):
                tok = emit(("name", word))
            elif re.fullmatch(rb"[+-]?(?:\d+\.?\d*|\.\d+)", word):
                tok = emit(("num", float(word)))
            else:
                if stack:
                    continue
                tok = ("op", word)
            if tok:
                yield tok
