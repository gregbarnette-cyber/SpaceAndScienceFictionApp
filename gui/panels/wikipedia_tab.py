"""gui/panels/wikipedia_tab.py — the shared Wikipedia article tab.

`WikipediaView` is the tab body (a QTextBrowser rendering the article's lead section + thumbnail,
fetched lazily on a background thread). `WikipediaButtonMixin` gives a panel a "📖 Wikipedia"
button plus the open/focus logic, and `open_or_focus_wiki_tab` adds/re-focuses the tab in any
QTabWidget. All six surfaces share this. See WIKIPEDIA_TABS_PLAN.md §6.
"""
import html
import os
import subprocess

from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextBrowser, QPushButton
from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage, QTextDocument, QDesktopServices

import core.wikipedia
from gui.panels.base import _BgDeliveryMixin, run_in_thread

_THUMB_RESOURCE = "wiki://thumbnail"


def _is_wsl():
    """True when running under WSL, where xdg-open usually has no browser installed."""
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open("/proc/version") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False


def _open_url_external(url):
    """Open *url* in the user's real browser.

    On WSL, Qt's QDesktopServices → xdg-open finds no Linux browser, so route to the Windows
    browser (wslview → PowerShell Start-Process → cmd start, first that launches wins). Everywhere
    else, use Qt's cross-platform opener.
    """
    if _is_wsl():
        for cmd in (
            ["wslview", url],
            ["powershell.exe", "-NoProfile", "-Command", "Start-Process '{}'".format(url)],
            ["cmd.exe", "/c", "start", "", url],
        ):
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except (FileNotFoundError, OSError):
                continue
    return bool(QDesktopServices.openUrl(QUrl(url)))


class WikipediaView(_BgDeliveryMixin, QWidget):
    """A lazily-fetched Wikipedia article view (lead section + thumbnail + external link).

    Inherits `_BgDeliveryMixin` so `run_in_thread` delivers results on the main thread — the
    QTextBrowser / QImage are only ever touched here.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self._browser = QTextBrowser()
        # Handle link clicks ourselves: Qt's setOpenExternalLinks → QDesktopServices → xdg-open,
        # which on WSL has no browser (see _open_url_external). setOpenLinks(False) also stops the
        # browser trying to navigate the document to a wiki URL it can't load.
        self._browser.setOpenLinks(False)
        self._browser.anchorClicked.connect(self._on_link)
        layout.addWidget(self._browser)
        self._star_label = ""
        self._article = None

    def load_for(self, *, name=None, designations=None, main_id=None, star_label=None):
        """Kick off the background resolve+fetch and show the loading state."""
        self._star_label = star_label or name or (main_id or "this star")
        self._browser.setHtml(self._html_loading())
        run_in_thread(
            self, core.wikipedia.resolve_and_fetch, (),
            {"designations": designations, "main_id": main_id, "name": name},
            on_result=self._on_article,
        )

    # ── background result handlers (main thread, via _BgDeliveryMixin) ────────
    def _on_article(self, res):
        if not isinstance(res, dict):
            self._browser.setHtml(self._html_error("Unexpected response."))
            return
        if "error" in res:
            self._browser.setHtml(self._html_error(res["error"]))
            return
        if not res.get("found"):
            self._browser.setHtml(self._html_not_found(res.get("tried") or []))
            return
        self._article = res
        self._browser.setHtml(self._html_found(res, with_image=False))
        thumb_url = res.get("thumbnail_url")
        if thumb_url:
            run_in_thread(
                self, core.wikipedia.fetch_thumbnail, (thumb_url,), {},
                on_result=self._on_thumb,
            )

    def _on_thumb(self, data):
        if not data or not self._article:
            return
        image = QImage()
        if not image.loadFromData(data):
            return
        # Register the image as a document resource, then re-render with an <img> that
        # references it. Order is addResource → setHtml (verified in this PySide6 build to keep
        # the resource retrievable after setHtml, so the <img> resolves). Best-effort — the text
        # already renders without it.
        self._browser.document().addResource(
            QTextDocument.ResourceType.ImageResource, QUrl(_THUMB_RESOURCE), image
        )
        self._browser.setHtml(self._html_found(self._article, with_image=True))

    def _on_link(self, qurl):
        """Open a clicked link in the real browser (WSL-aware). Relative /wiki/ links from the
        article body are resolved against en.wikipedia.org; in-page fragments are ignored."""
        url = qurl.toString()
        if not url or url.startswith("#"):
            return
        if url.startswith("/"):
            url = "https://en.wikipedia.org" + url
        if url.startswith("http://") or url.startswith("https://"):
            _open_url_external(url)

    # ── HTML render helpers (QTextBrowser-safe subset) ────────────────────────
    def _html_loading(self):
        return (
            "<div style='margin:6px'>"
            "<p style='color:gray'><i>Loading “{}” from Wikipedia…</i></p>"
            "</div>".format(html.escape(self._star_label))
        )

    def _html_error(self, msg):
        return (
            "<div style='margin:6px'>"
            "<p style='color:#b23a2e'><b>Couldn't load the Wikipedia article.</b></p>"
            "<p style='color:#b23a2e'>{}</p>"
            "</div>".format(html.escape(str(msg)))
        )

    def _html_not_found(self, tried):
        tried_txt = ", ".join(html.escape(t) for t in tried) if tried else "—"
        return (
            "<div style='margin:6px'>"
            "<h3>No Wikipedia article found</h3>"
            "<p>No Wikipedia article could be matched for <b>{}</b>.</p>"
            "<p style='color:gray; font-size:small'>Tried: {}</p>"
            "</div>".format(html.escape(self._star_label), tried_txt)
        )

    def _html_found(self, res, with_image=False):
        title = html.escape(res.get("title") or self._star_label)
        desc = res.get("description") or ""
        matched = res.get("matched_on") or ""
        url = res.get("url") or ""
        extract_html = res.get("extract_html") or ""
        img = ("<img src='{}' style='float:right; margin:0 0 8px 12px' width='150'>".format(_THUMB_RESOURCE)
               if with_image else "")
        sub_bits = []
        if desc:
            sub_bits.append("<i>{}</i>".format(html.escape(desc)))
        if matched:
            sub_bits.append("matched on “{}”".format(html.escape(matched)))
        sub = ("<p style='color:gray; font-size:small'>{}</p>".format(" · ".join(sub_bits))
               if sub_bits else "")
        link = ("<p><a href='{}'>Read the full article on Wikipedia ↗</a></p>".format(html.escape(url))
                if url else "")
        return (
            "<div style='margin:6px'>"
            "{img}"
            "<h2 style='margin-bottom:2px'>{title}</h2>"
            "{sub}"
            "{body}"
            "{link}"
            "<p style='color:gray; font-size:x-small'>Text from Wikipedia, CC BY-SA.</p>"
            "</div>".format(img=img, title=title, sub=sub, body=extract_html, link=link)
        )


def open_or_focus_wiki_tab(tabs, star_label, *, designations=None, main_id=None, name=None):
    """Open (or re-focus) a '📖 {star_label} — Wikipedia' tab in the given QTabWidget.

    If a tab with that title already exists it is focused; otherwise a fresh WikipediaView is
    created, loaded, added and selected. Closability is the host tab widget's choice, not this
    function's: the catalog panels (opts 1–7) add the tab to their Data/Hypatia tab strip, which
    is not `setTabsClosable`, so the article sits there like the GCNS/Hypatia tabs and is replaced
    on the next search; opts 18/19's results tab widget IS closable (with index-0 protected), so
    there the article tab carries a close button.
    """
    title = "📖 {} — Wikipedia".format(star_label or "star")
    for i in range(tabs.count()):
        if tabs.tabText(i) == title:
            tabs.setCurrentIndex(i)
            return tabs.widget(i)
    view = WikipediaView()
    view.load_for(name=name, designations=designations, main_id=main_id, star_label=star_label)
    idx = tabs.addTab(view, title)
    tabs.setCurrentIndex(idx)
    return view


class WikipediaButtonMixin:
    """Adds a '📖 Wikipedia' button + open/focus logic to a panel.

    Contract: call `self._make_wiki_button()` in build_inputs and place the returned button;
    call `self._set_wiki_context(tabs, …)` after a successful render to point the button at the
    star and enable it. `_open_wikipedia` opens/focuses the tab in the stored tab widget.
    """

    def _make_wiki_button(self, label="📖 Wikipedia"):
        btn = QPushButton(label)
        btn.setEnabled(False)
        btn.clicked.connect(self._open_wikipedia)
        self._wiki_btn = btn
        return btn

    def _set_wiki_context(self, tabs, *, designations=None, main_id=None, name=None, star_label=None):
        self._wiki_ctx = {
            "tabs": tabs, "designations": designations, "main_id": main_id,
            "name": name, "star_label": star_label,
        }
        if getattr(self, "_wiki_btn", None) is not None:
            self._wiki_btn.setEnabled(True)

    def _open_wikipedia(self):
        ctx = getattr(self, "_wiki_ctx", None)
        if not ctx or ctx.get("tabs") is None:
            return
        try:
            open_or_focus_wiki_tab(
                ctx["tabs"], ctx.get("star_label"),
                designations=ctx.get("designations"), main_id=ctx.get("main_id"),
                name=ctx.get("name"),
            )
        except RuntimeError:
            # The target tab widget was deleted (e.g. a new search landed mid-click). Disable
            # the button; the next successful render re-arms it via _set_wiki_context.
            btn = getattr(self, "_wiki_btn", None)
            if btn is not None:
                btn.setEnabled(False)
