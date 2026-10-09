from __future__ import annotations

import hashlib
import http.client
import ipaddress
import re
import socket
import ssl
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Protocol
from urllib.parse import urljoin, urlsplit, urlunsplit

DIRECT_HOSTS = frozenset({"xiaohongshu.com", "www.xiaohongshu.com"})
SHORT_HOSTS = frozenset({"xhslink.com", "www.xhslink.com"})
ALLOWED_HOSTS = DIRECT_HOSTS | SHORT_HOSTS
MEDIA_HOST = "xhscdn.com"
REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
URL_PATTERN = re.compile(r"https?://[^\s<>\"'，。；：！？、）》】}\)\]]+", re.IGNORECASE)
NOTE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
SHORT_PATH_PATTERN = re.compile(r"^/[A-Za-z0-9_./~-]{1,240}$")
TRAILING_PUNCTUATION = ".,;:!?，。；：！？、）》】})]"


class XiaohongshuLinkError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 422):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class ParsedLink:
    request_url: str
    normalized_url: str
    kind: str
    note_id: str | None


@dataclass(frozen=True)
class MetadataResponse:
    status: int
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class LinkMetadata:
    canonical_url: str | None
    note_id: str | None
    title: str | None
    description: str | None
    author: str | None
    thumbnail_present: bool
    media_candidates: tuple[MediaCandidate, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class MediaCandidate:
    candidate_id: str
    position: int
    role: str
    source_url: str = field(repr=False)


@dataclass(frozen=True)
class DownloadedImage:
    candidate_id: str
    body: bytes
    content_type: str
    filename: str


class MetadataTransport(Protocol):
    def fetch(self, url: str, *, timeout: float, max_bytes: int) -> MetadataResponse: ...


class MediaTransport(Protocol):
    def fetch(self, url: str, *, timeout: float, max_bytes: int) -> MetadataResponse: ...


def parse_share_text(share_text: str) -> ParsedLink:
    matches = [
        match.group(0).rstrip(TRAILING_PUNCTUATION) for match in URL_PATTERN.finditer(share_text)
    ]
    if not matches:
        raise XiaohongshuLinkError("XHS_LINK_NOT_FOUND", "没有找到 HTTPS 小红书链接。")
    if len(matches) != 1:
        raise XiaohongshuLinkError("XHS_MULTIPLE_LINKS", "一次只能解析一个分享链接。")
    return parse_url(matches[0])


def parse_url(url: str) -> ParsedLink:
    if len(url) > 2048:
        raise XiaohongshuLinkError("XHS_LINK_INVALID", "链接过长。")
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").encode("idna").decode("ascii").lower()
        port = parts.port
    except (UnicodeError, ValueError) as exc:
        raise XiaohongshuLinkError("XHS_LINK_INVALID", "链接格式无效。") from exc
    if parts.scheme.lower() != "https":
        raise XiaohongshuLinkError("XHS_HTTPS_REQUIRED", "只接受 HTTPS 分享链接。")
    if parts.username is not None or parts.password is not None or port not in {None, 443}:
        raise XiaohongshuLinkError("XHS_LINK_INVALID", "链接包含不允许的认证信息或端口。")
    if host not in ALLOWED_HOSTS:
        raise XiaohongshuLinkError("XHS_HOST_NOT_ALLOWED", "链接不是受支持的小红书域名。")
    if parts.fragment:
        parts = parts._replace(fragment="")
    path = parts.path or "/"
    request_url = urlunsplit(("https", host, path, parts.query, ""))
    normalized_url = urlunsplit(("https", host, path, "", ""))
    if host in SHORT_HOSTS:
        if path == "/" or not SHORT_PATH_PATTERN.fullmatch(path):
            raise XiaohongshuLinkError("XHS_LINK_INVALID", "小红书短链接路径无效。")
        return ParsedLink(request_url, normalized_url, "short", None)
    note_id = _note_id_from_path(path)
    if note_id is None:
        raise XiaohongshuLinkError("XHS_NOTE_PATH_UNSUPPORTED", "链接不是受支持的小红书笔记地址。")
    canonical = f"https://www.xiaohongshu.com/explore/{note_id}"
    return ParsedLink(request_url, canonical, "direct", note_id)


def _note_id_from_path(path: str) -> str | None:
    segments = [segment for segment in path.split("/") if segment]
    candidate: str | None = None
    if len(segments) == 2 and segments[0] in {"explore", "item"}:
        candidate = segments[1]
    elif len(segments) == 3 and segments[:2] == ["discovery", "item"]:
        candidate = segments[2]
    if candidate and NOTE_ID_PATTERN.fullmatch(candidate):
        return candidate
    return None


class _MetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.meta: dict[str, str] = {}
        self.media_urls: list[tuple[str, str]] = []
        self.canonical: str | None = None
        self.title_parts: list[str] = []
        self._in_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value for key, value in attrs if value is not None}
        if tag.lower() == "meta":
            key = (values.get("property") or values.get("name") or "").lower()
            content = values.get("content", "").strip()
            if key in {"og:image", "og:image:url", "twitter:image"} and content:
                self.media_urls.append((key, content))
            if key and content and key not in self.meta:
                self.meta[key] = content
        elif tag.lower() == "link" and "canonical" in values.get("rel", "").lower().split():
            self.canonical = values.get("href")
        elif tag.lower() == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title and sum(map(len, self.title_parts)) < 500:
            self.title_parts.append(data)


def extract_metadata(body: bytes, page_url: str) -> LinkMetadata:
    parser = _MetadataParser()
    parser.feed(body.decode("utf-8", errors="replace"))
    warnings: list[str] = []
    canonical_link = parser.meta.get("og:url") or parser.canonical
    parsed_page = parse_url(page_url)
    canonical_url = parsed_page.normalized_url if parsed_page.kind == "direct" else None
    note_id = parsed_page.note_id
    if canonical_link:
        try:
            parsed_canonical = parse_url(urljoin(page_url, canonical_link))
            if parsed_canonical.kind == "direct":
                canonical_url = parsed_canonical.normalized_url
                note_id = parsed_canonical.note_id
        except XiaohongshuLinkError:
            warnings.append("页面提供的 canonical 地址不在受支持范围内，已忽略。")
    title = parser.meta.get("og:title") or "".join(parser.title_parts).strip() or None
    description = parser.meta.get("og:description") or parser.meta.get("description") or None
    author = parser.meta.get("author") or parser.meta.get("article:author") or None
    candidates: list[MediaCandidate] = []
    seen_urls: set[str] = set()
    for _, media_url in parser.media_urls:
        try:
            normalized_media = parse_media_url(urljoin(page_url, media_url))
        except XiaohongshuLinkError:
            warnings.append("页面提供了不受支持的图片地址，已忽略。")
            continue
        if normalized_media in seen_urls:
            continue
        seen_urls.add(normalized_media)
        candidates.append(
            MediaCandidate(
                candidate_id=_media_candidate_id(normalized_media),
                position=len(candidates) + 1,
                role="cover",
                source_url=normalized_media,
            )
        )
        if len(candidates) == 20:
            warnings.append("页面图片候选超过 20 个，仅保留前 20 个。")
            break
    return LinkMetadata(
        canonical_url=canonical_url,
        note_id=note_id,
        title=_clean_text(title, 200),
        description=_clean_text(description, 500),
        author=_clean_text(author, 100),
        thumbnail_present=bool(candidates),
        media_candidates=tuple(candidates),
        warnings=tuple(warnings),
    )


def parse_media_url(url: str) -> str:
    if len(url) > 4096:
        raise XiaohongshuLinkError("XHS_MEDIA_URL_INVALID", "图片地址过长。")
    try:
        parts = urlsplit(url)
        host = (parts.hostname or "").encode("idna").decode("ascii").lower()
        port = parts.port
    except (UnicodeError, ValueError) as exc:
        raise XiaohongshuLinkError("XHS_MEDIA_URL_INVALID", "图片地址格式无效。") from exc
    if parts.scheme.lower() != "https":
        raise XiaohongshuLinkError("XHS_MEDIA_HTTPS_REQUIRED", "图片地址必须使用 HTTPS。")
    if parts.username is not None or parts.password is not None or port not in {None, 443}:
        raise XiaohongshuLinkError("XHS_MEDIA_URL_INVALID", "图片地址包含不允许的信息。")
    if host != MEDIA_HOST and not host.endswith(f".{MEDIA_HOST}"):
        raise XiaohongshuLinkError("XHS_MEDIA_HOST_NOT_ALLOWED", "图片地址不在受支持的 CDN。")
    if not parts.path or parts.path == "/":
        raise XiaohongshuLinkError("XHS_MEDIA_URL_INVALID", "图片地址缺少资源路径。")
    return urlunsplit(("https", host, parts.path, parts.query, ""))


def _media_candidate_id(url: str) -> str:
    return "xhs-image-" + hashlib.sha256(url.encode()).hexdigest()[:20]


def _clean_text(value: str | None, limit: int) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split())
    return cleaned[:limit] or None


class _PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, host: str, ip: str, *, timeout: float):
        super().__init__(host, port=443, timeout=timeout, context=ssl.create_default_context())
        self._ip = ip

    def connect(self) -> None:
        raw_socket = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)


class PublicHttpsTransport:
    """Fetch one validated HTTPS page while pinning the checked public IP address."""

    user_agent = "wmrm-metadata-preview/0.1"

    def fetch(self, url: str, *, timeout: float, max_bytes: int) -> MetadataResponse:
        parsed = parse_url(url)
        parts = urlsplit(parsed.request_url)
        host = parts.hostname or ""
        ip = _resolve_public_ip(host)
        target = urlunsplit(("", "", parts.path or "/", parts.query, ""))
        connection = _PinnedHTTPSConnection(host, ip, timeout=timeout)
        try:
            connection.request(
                "GET",
                target,
                headers={
                    "Accept": "text/html,application/xhtml+xml",
                    "User-Agent": self.user_agent,
                },
            )
            response = connection.getresponse()
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise XiaohongshuLinkError("XHS_PAGE_TOO_LARGE", "页面超过元数据读取上限。", 502)
            return MetadataResponse(
                response.status,
                {key.lower(): value for key, value in response.getheaders()},
                body,
            )
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise XiaohongshuLinkError(
                "XHS_METADATA_UNAVAILABLE", "暂时无法读取页面元数据。", 502
            ) from exc
        finally:
            connection.close()


class PublicMediaTransport:
    """Fetch one validated Xiaohongshu CDN image while pinning a checked public IP."""

    user_agent = "wmrm-media-import/0.1"

    def fetch(self, url: str, *, timeout: float, max_bytes: int) -> MetadataResponse:
        normalized = parse_media_url(url)
        parts = urlsplit(normalized)
        host = parts.hostname or ""
        ip = _resolve_public_ip(host)
        target = urlunsplit(("", "", parts.path or "/", parts.query, ""))
        connection = _PinnedHTTPSConnection(host, ip, timeout=timeout)
        try:
            connection.request(
                "GET",
                target,
                headers={
                    "Accept": "image/avif,image/webp,image/png,image/jpeg",
                    "User-Agent": self.user_agent,
                },
            )
            response = connection.getresponse()
            body = response.read(max_bytes + 1)
            if len(body) > max_bytes:
                raise XiaohongshuLinkError("XHS_MEDIA_TOO_LARGE", "图片超过导入大小限制。", 413)
            return MetadataResponse(
                response.status,
                {key.lower(): value for key, value in response.getheaders()},
                body,
            )
        except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
            raise XiaohongshuLinkError("XHS_MEDIA_UNAVAILABLE", "暂时无法下载图片。", 502) from exc
        finally:
            connection.close()


def _resolve_public_ip(host: str) -> str:
    try:
        addresses = {item[4][0] for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise XiaohongshuLinkError(
            "XHS_METADATA_UNAVAILABLE", "无法解析分享链接域名。", 502
        ) from exc
    if not addresses:
        raise XiaohongshuLinkError("XHS_METADATA_UNAVAILABLE", "无法解析分享链接域名。", 502)
    parsed_addresses = [ipaddress.ip_address(address) for address in addresses]
    if any(not address.is_global for address in parsed_addresses):
        raise XiaohongshuLinkError("XHS_UNSAFE_ADDRESS", "分享链接解析到了非公网地址。", 422)
    return str(sorted(parsed_addresses, key=lambda address: (address.version, int(address)))[0])


def resolve_metadata(
    parsed: ParsedLink,
    transport: MetadataTransport,
    *,
    timeout: float,
    max_bytes: int,
    max_redirects: int,
) -> LinkMetadata:
    current = parsed.request_url
    for redirect_count in range(max_redirects + 1):
        response = transport.fetch(current, timeout=timeout, max_bytes=max_bytes)
        if response.status in REDIRECT_STATUSES:
            if redirect_count == max_redirects:
                raise XiaohongshuLinkError(
                    "XHS_TOO_MANY_REDIRECTS", "分享链接重定向次数过多。", 502
                )
            location = response.headers.get("location")
            if not location:
                raise XiaohongshuLinkError(
                    "XHS_INVALID_REDIRECT", "分享链接重定向缺少目标地址。", 502
                )
            current = parse_url(urljoin(current, location)).request_url
            continue
        if response.status != 200:
            raise XiaohongshuLinkError(
                "XHS_METADATA_UNAVAILABLE", "页面未返回可读取的元数据。", 502
            )
        content_type = response.headers.get("content-type", "").lower()
        if not (
            content_type.startswith("text/html") or content_type.startswith("application/xhtml+xml")
        ):
            raise XiaohongshuLinkError(
                "XHS_CONTENT_TYPE_UNSUPPORTED", "页面不是 HTML，未读取内容。", 502
            )
        final_link = parse_url(current)
        if final_link.kind != "direct":
            raise XiaohongshuLinkError(
                "XHS_SHORT_LINK_UNRESOLVED", "短链接没有跳转到受支持的笔记地址。", 502
            )
        return extract_metadata(response.body, current)
    raise AssertionError("redirect loop exhausted")


def download_image(
    candidate: MediaCandidate,
    transport: MediaTransport,
    *,
    timeout: float,
    max_bytes: int,
    max_redirects: int,
) -> DownloadedImage:
    current = candidate.source_url
    for redirect_count in range(max_redirects + 1):
        response = transport.fetch(current, timeout=timeout, max_bytes=max_bytes)
        if response.status in REDIRECT_STATUSES:
            if redirect_count == max_redirects:
                raise XiaohongshuLinkError(
                    "XHS_MEDIA_TOO_MANY_REDIRECTS", "图片重定向次数过多。", 502
                )
            location = response.headers.get("location")
            if not location:
                raise XiaohongshuLinkError(
                    "XHS_MEDIA_INVALID_REDIRECT", "图片重定向缺少地址。", 502
                )
            current = parse_media_url(urljoin(current, location))
            continue
        if response.status != 200:
            raise XiaohongshuLinkError("XHS_MEDIA_UNAVAILABLE", "图片服务器未返回可下载内容。", 502)
        content_type = response.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        extensions = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }
        extension = extensions.get(content_type)
        if extension is None:
            raise XiaohongshuLinkError(
                "XHS_MEDIA_TYPE_UNSUPPORTED", "只支持 JPEG、PNG 和 WebP 图片。", 415
            )
        if not response.body:
            raise XiaohongshuLinkError("XHS_MEDIA_INVALID", "下载到的图片为空。", 422)
        return DownloadedImage(
            candidate_id=candidate.candidate_id,
            body=response.body,
            content_type=content_type,
            filename=f"xiaohongshu-{candidate.position}.{extension}",
        )
    raise AssertionError("redirect loop exhausted")
