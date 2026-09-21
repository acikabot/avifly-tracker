"""The project's own Markdown files, rendered inside the app.

Only files that ship with the code are listed (``README.md`` and everything in
``docs/``) — never a path a visitor can choose — and each one is re-rendered when the
file on disk changes, so the pages always match the repository. Images the documents
use live in ``docs/images/`` and are served by this module too.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import markdown
from django.conf import settings
from django.urls import reverse

#: Where the Markdown lives, relative to the project root.
SOURCES: tuple[Path, ...] = (Path("README.md"), Path("docs"))

#: Images the documents may show, and the types served.
IMAGE_DIR = Path("docs/images")
IMAGE_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".svg": "image/svg+xml",
}

EXTENSIONS = ["tables", "fenced_code", "toc", "sane_lists", "attr_list", "def_list"]
#: The "on this page" list is built from the section headings, not the document title.
EXTENSION_CONFIG = {"toc": {"toc_depth": "2-3"}}
_LINK_TO_MD = re.compile(r'href="(?!https?://)([^"#]+\.md)(#[^"]*)?"')
_HEADING = re.compile(r"^#\s+(.+)$", re.M)
_IMG = re.compile(r"<img\b[^>]*>")
_ATTR = re.compile(r'([\w-]+)="([^"]*)"')


@dataclass(frozen=True)
class Document:
    slug: str
    path: Path
    title: str
    summary: str
    #: Files whose name starts with "_" are private notes: owners only.
    owner_only: bool = False

    @property
    def url(self) -> str:
        return reverse("docs:page", args=[self.slug])


@dataclass(frozen=True)
class RenderedDocument:
    document: Document
    html: str
    toc: str


def _slug_for(path: Path) -> str:
    return "guide" if path.name == "README.md" else path.stem.lower().lstrip("_")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _title_and_summary(text: str, fallback: str) -> tuple[str, str]:
    heading = _HEADING.search(text)
    title = heading.group(1).strip() if heading else fallback
    body = text[heading.end() :] if heading else text
    summary = ""
    for block in body.split("\n\n"):
        block = block.strip()
        if block and not block.startswith(("#", "|", "```", "<", "-", "*", "!")):
            summary = " ".join(block.replace("`", "").replace("*", "").split())
            break
    return title, summary


def _markdown_files() -> list[Path]:
    root = Path(settings.BASE_DIR)
    files: list[Path] = []
    for source in SOURCES:
        full = root / source
        if full.is_dir():
            files.extend(sorted(p for p in full.glob("*.md")))
        elif full.is_file():
            files.append(full)
    return files


def documents() -> dict[str, Document]:
    """Every document that ships with the code, keyed by slug."""
    found: dict[str, Document] = {}
    for path in _markdown_files():
        slug = _slug_for(path)
        title, summary = _title_and_summary(_read(path), path.stem)
        found[slug] = Document(
            slug=slug,
            path=path,
            title=title,
            summary=summary,
            owner_only=path.name.startswith("_"),
        )
    return found


def documents_for(user) -> dict[str, Document]:
    """The documents ``user`` may read (private notes are owners-only)."""
    return {
        slug: document
        for slug, document in documents().items()
        if not document.owner_only or user.is_superuser
    }


def get_document(slug: str, user=None) -> Document | None:
    available = documents() if user is None else documents_for(user)
    return available.get(slug)


_cache: dict[str, tuple[float, RenderedDocument]] = {}


def render(document: Document) -> RenderedDocument:
    """Render a document to HTML, re-using the last result until the file changes."""
    stamp = document.path.stat().st_mtime
    cached = _cache.get(document.slug)
    if cached and cached[0] == stamp:
        return cached[1]

    converter = markdown.Markdown(
        extensions=EXTENSIONS, extension_configs=EXTENSION_CONFIG, output_format="html"
    )
    html = converter.convert(_read(document.path))
    html = _fix_images(_fix_links(html), document)
    rendered = RenderedDocument(document=document, html=html, toc=converter.toc)
    _cache[document.slug] = (stamp, rendered)
    return rendered


def _fix_links(html: str) -> str:
    """Point links between Markdown files at their pages in the app."""
    known = {str(doc.path.name): doc for doc in documents().values()}

    def replace(match: re.Match) -> str:
        target, anchor = match.group(1), match.group(2) or ""
        document = known.get(Path(target).name)
        if document is None:
            return match.group(0)
        return f'href="{document.url}{anchor}"'

    return _LINK_TO_MD.sub(replace, html)


def image_path(name: str) -> Path | None:
    """The file ``name`` in ``docs/images/``, or None — never anything outside it."""
    folder = (Path(settings.BASE_DIR) / IMAGE_DIR).resolve()
    candidate = (folder / name).resolve()
    if candidate.parent != folder or candidate.suffix.lower() not in IMAGE_TYPES:
        return None
    return candidate if candidate.is_file() else None


def _fix_images(html: str, document: Document) -> str:
    """Serve the documents' own images from here; show other sites' images as labels.

    Paths are written relative to the Markdown file (so they work on GitHub too). The
    Content-Security-Policy blocks images from other sites, such as README badges, so
    those become small text labels instead of broken pictures.
    """
    folder = (Path(settings.BASE_DIR) / IMAGE_DIR).resolve()

    def replace(match: re.Match) -> str:
        tag = match.group(0)
        attrs = dict(_ATTR.findall(tag))
        src, alt = attrs.get("src", ""), attrs.get("alt", "")
        if src.startswith(("http://", "https://", "//")):
            return f'<span class="badge text-bg-light border">{alt}</span>' if alt else ""
        target = (document.path.parent / src).resolve()
        if target.parent == folder and image_path(target.name):
            url = reverse("docs:image", args=[target.name])
            return tag.replace(f'src="{src}"', f'src="{url}"', 1)
        return tag

    return _IMG.sub(replace, html)
