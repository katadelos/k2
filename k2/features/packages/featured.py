"""Remote, declarative app recommendations and their same-server artwork."""

import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urljoin, urlsplit

import certifi
from PyQt5.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QObject,
    QTimer,
    QUrl,
    pyqtProperty,
    pyqtSignal,
    pyqtSlot,
)
from PyQt5.QtGui import QImageReader
from PyQt5.QtNetwork import (
    QNetworkAccessManager,
    QNetworkReply,
    QNetworkRequest,
    QSslCertificate,
    QSslConfiguration,
)

DEFAULT_CATALOG_URL = (
    "https://raw.githubusercontent.com/katadelos/k2/main/feed/featured/index.json"
)
MAX_CATALOG_BYTES = 128 * 1024
MAX_IMAGE_BYTES = 2 * 1024 * 1024
MAX_ITEMS = 20
PACKAGE_NAME = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9.+_-]{0,127}\Z")
ITEM_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}\Z")


def _origin(url):
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Featured URLs must use HTTP or HTTPS.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Featured URLs cannot contain credentials.")
    return (
        parsed.scheme,
        parsed.hostname.lower(),
        parsed.port or (443 if parsed.scheme == "https" else 80),
    )


def catalog_url():
    """Use the public K2 catalogue unless an explicit URL is configured."""
    return os.environ.get("K2_FEATURED_URL", DEFAULT_CATALOG_URL).strip()


def _text(value, field, limit, *, optional=False):
    if optional and value is None:
        return ""
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"Featured {field} must contain 1–{limit} characters.")
    return value.strip()


def parse_catalog(data, url):
    """Validate content before exposing it to QML or making image requests."""
    try:
        catalog = json.loads(data)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ValueError("The Featured file is not valid JSON.") from error
    if (
        not isinstance(catalog, dict)
        or set(catalog) != {"schema", "items"}
        or type(catalog["schema"]) is not int
        or catalog["schema"] != 1
        or not isinstance(catalog["items"], list)
        or len(catalog["items"]) > MAX_ITEMS
    ):
        raise ValueError("Featured requires schema 1 and up to 20 items.")
    origin = _origin(url)
    items = []
    identifiers = set()
    for entry in catalog["items"]:
        if not isinstance(entry, dict) or not set(entry) <= {
            "id",
            "width",
            "title",
            "headline",
            "description",
            "image",
            "action",
        }:
            raise ValueError("A Featured item contains unknown fields.")
        identifier = entry.get("id", "")
        if (
            not isinstance(identifier, str)
            or not ITEM_ID.fullmatch(identifier)
            or identifier in identifiers
        ):
            raise ValueError("Featured items need unique alphanumeric IDs.")
        identifiers.add(identifier)
        width = entry.get("width")
        if width not in ("full", "half"):
            raise ValueError("Featured item width must be full or half.")
        action = entry.get("action")
        if not isinstance(action, dict) or set(action) not in (
            {"label", "route"},
            {"label", "package"},
        ):
            raise ValueError(
                "Featured actions need a label and either route or package."
            )
        label = _text(action["label"], "action label", 60)
        if "route" in action:
            if action["route"] != "koreader":
                raise ValueError("The Featured route is not supported.")
            action = {"label": label, "route": "koreader"}
        else:
            package = action["package"]
            if not isinstance(package, str) or not PACKAGE_NAME.fullmatch(package):
                raise ValueError("The Featured package name is invalid.")
            action = {"label": label, "package": package}
        image = _text(entry.get("image"), "image URL", 2048, optional=True)
        if image:
            image = urljoin(url, image)
            if _origin(image) != origin:
                raise ValueError(
                    "Featured artwork must use the same server as its JSON."
                )
        items.append(
            {
                "id": identifier,
                "width": width,
                "title": _text(entry.get("title"), "title", 80),
                "headline": _text(
                    entry.get("headline"), "headline", 160, optional=True
                ),
                "description": _text(entry.get("description"), "description", 500),
                "image": image,
                "action": action,
            }
        )
    return items


class _Download(QObject):
    """One bounded Qt request, including any redirects on the same origin."""

    completed = pyqtSignal(object, str, str)

    def __init__(self, manager, url, limit, tls, parent):
        super().__init__(parent)
        self._manager = manager
        self._origin = _origin(url)
        self._limit = limit
        self._tls = tls
        self._body = bytearray()
        self._error = ""
        self._redirects = 0
        self._cancelled = False
        self._reply = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(15000)
        self._timer.timeout.connect(self._timed_out)
        self._url = url

    def start(self):
        self._timer.start()
        self._request(self._url)

    def _request(self, url):
        self._url = url
        self._body.clear()
        request = QNetworkRequest(QUrl(url))
        if self._tls is not None:
            request.setSslConfiguration(self._tls)
        request.setAttribute(
            QNetworkRequest.RedirectPolicyAttribute,
            QNetworkRequest.ManualRedirectPolicy,
        )
        self._reply = self._manager.get(request)
        self._reply.setReadBufferSize(self._limit + 1)
        self._reply.readyRead.connect(self._read)
        self._reply.finished.connect(self._finished)

    @pyqtSlot()
    def _read(self):
        if self._cancelled or self._error or self._reply is None:
            return
        chunk = self._reply.read(self._limit + 1 - len(self._body))
        if chunk:
            self._body.extend(bytes(chunk))
        if len(self._body) > self._limit:
            self._error = "The Featured download is too large."
            self._reply.abort()

    @pyqtSlot()
    def _timed_out(self):
        self._error = "The Featured server took too long to respond."
        if self._reply is not None:
            self._reply.abort()

    @pyqtSlot()
    def _finished(self):
        reply = self._reply
        if reply is None:
            return
        reply.deleteLater()
        if self._cancelled:
            return
        self._read()
        redirect = reply.attribute(QNetworkRequest.RedirectionTargetAttribute)
        if not self._error and redirect is not None:
            target = reply.url().resolved(redirect).toString()
            try:
                if _origin(target) != self._origin or self._redirects >= 3:
                    raise ValueError(
                        "The Featured server redirected to an unsupported URL."
                    )
            except ValueError as error:
                self._error = str(error)
            else:
                self._redirects += 1
                self._request(target)
                return
        if not self._error:
            status = reply.attribute(QNetworkRequest.HttpStatusCodeAttribute)
            if (
                reply.error() != QNetworkReply.NoError
                or not status
                or not 200 <= status < 300
            ):
                self._error = "Could not load Featured content from the server."
        self._timer.stop()
        self.completed.emit(bytes(self._body), self._error, self._url)

    def cancel(self):
        self._cancelled = True
        self._timer.stop()
        if self._reply is not None:
            self._reply.abort()
            self._reply.deleteLater()


class FeaturedCatalog(QObject):
    changed = pyqtSignal()

    def __init__(self, url, parent=None):
        super().__init__(parent)
        self._url = url
        self._items = []
        self._loading = False
        self._error = ""
        self._manager = QNetworkAccessManager(self)
        self._tls = None
        self._download = None
        self._artwork = None
        self._pending_images = []
        self._image_items = {}
        self._image_url = ""
        self._image_errors = False
        self._stopped = False
        self._artwork_timer = QTimer(self)
        self._artwork_timer.setSingleShot(True)
        self._artwork_timer.setInterval(15000)
        self._artwork_timer.timeout.connect(self._artwork_timed_out)

    @pyqtProperty("QVariantList", notify=changed)
    def items(self):
        return self._items

    @pyqtProperty(bool, notify=changed)
    def loading(self):
        return self._loading

    @pyqtProperty(str, notify=changed)
    def error(self):
        return self._error

    @pyqtProperty(bool, constant=True)
    def configured(self):
        return bool(self._url)

    @pyqtSlot()
    def refresh(self):
        if self._stopped or self._loading or not self._url:
            return
        self._items = []
        self._error = ""
        self._image_errors = False
        self._pending_images = []
        self._image_items = {}
        if self._artwork is not None:
            self._artwork.cleanup()
            self._artwork = None
        self._loading = True
        self.changed.emit()
        try:
            self._fetch(self._url, MAX_CATALOG_BYTES, self._catalog_downloaded)
        except ValueError as error:
            self._finish(str(error))

    def _fetch(self, url, limit, callback):
        if _origin(url)[0] == "https" and self._tls is None:
            self._tls = QSslConfiguration.defaultConfiguration()
            self._tls.setCaCertificates(
                self._tls.caCertificates() + QSslCertificate.fromPath(certifi.where())
            )
        self._download = _Download(self._manager, url, limit, self._tls, self)
        self._download.completed.connect(callback)
        self._download.start()

    def _release_download(self):
        if self._download is not None:
            self._download.deleteLater()
            self._download = None

    @pyqtSlot(object, str, str)
    def _catalog_downloaded(self, data, error, url):
        self._release_download()
        if error:
            self._finish(error)
            return
        try:
            self._items = parse_catalog(data, url)
        except ValueError as error:
            self._items = []
            self._finish(str(error))
            return
        for item in self._items:
            if item["image"]:
                self._image_items.setdefault(item["image"], []).append(item)
                item["image"] = ""
        self._pending_images = list(self._image_items)
        self.changed.emit()
        if self._pending_images:
            try:
                self._artwork = TemporaryDirectory(prefix="k2-featured-")
            except OSError:
                self._finish("Featured artwork could not be saved.")
                return
            self._artwork_timer.start()
        self._next_image()

    def _next_image(self):
        if not self._pending_images:
            self._finish(
                "Some Featured artwork could not load." if self._image_errors else ""
            )
            return
        self._image_url = self._pending_images.pop(0)
        self._fetch(self._image_url, MAX_IMAGE_BYTES, self._image_downloaded)

    @pyqtSlot(object, str, str)
    def _image_downloaded(self, data, error, url):
        self._release_download()
        local_url = ""
        if not error:
            try:
                buffer = QBuffer()
                buffer.setData(QByteArray(data))
                buffer.open(QIODevice.ReadOnly)
                reader = QImageReader(buffer)
                size = reader.size()
                extension = bytes(reader.format()).decode("ascii")
                if (
                    extension not in {"png", "jpeg", "webp"}
                    or not reader.canRead()
                    or size.width() <= 0
                    or size.height() <= 0
                    or size.width() > 2048
                    or size.height() > 2048
                ):
                    raise ValueError("Unsupported Featured artwork.")
                if self._artwork is None:
                    raise ValueError("Featured artwork storage is unavailable.")
                image = (
                    Path(self._artwork.name)
                    / f"{len(self._pending_images)}.{extension}"
                )
                image.write_bytes(data)
                local_url = QUrl.fromLocalFile(str(image)).toString()
            except OSError, UnicodeError, ValueError:
                self._image_errors = True
        else:
            self._image_errors = True
        for item in self._image_items[self._image_url]:
            item["image"] = local_url
        self.changed.emit()
        self._next_image()

    @pyqtSlot()
    def _artwork_timed_out(self):
        if self._download is not None:
            self._download.cancel()
            self._release_download()
        self._pending_images = []
        self._finish("Some Featured artwork could not load.")

    def _finish(self, error):
        self._artwork_timer.stop()
        self._loading = False
        self._error = error
        self.changed.emit()

    def stop(self):
        self._stopped = True
        self._artwork_timer.stop()
        if self._download is not None:
            self._download.cancel()
            self._release_download()
        self._pending_images = []
        self._loading = False

    def close(self):
        self.stop()
        if self._artwork is not None:
            self._artwork.cleanup()
            self._artwork = None
