"""Backend module for PureArt — handles iTunes Search API calls and artwork downloads."""

from __future__ import annotations

import io
import re
from datetime import datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal, TypedDict

import requests
from PIL import Image as PILImage


BASE_URL = "https://itunes.apple.com/search"
SearchType = Literal["album", "song", "artist"]
ArtworkQuality = Literal["low", "medium", "high"]

ARTWORK_DIMENSIONS: dict[ArtworkQuality, str] = {
    "low": "600x600",
    "medium": "1280x1280",
    "high": "10000x10000",
}


class ArtworkResult(TypedDict):
    artist_name: str
    collection_name: str
    release_year: str
    artwork_link: str
    preview_url: str


class ArtworkError(Exception):
    """Base class for artwork-related failures."""


class ArtworkSearchError(ArtworkError):
    """Raised when the iTunes search request cannot be completed."""


class ArtworkDownloadError(ArtworkError):
    """Raised when artwork cannot be downloaded or saved."""


class ArtworkPreviewError(ArtworkError):
    """Raised when an artwork preview cannot be fetched."""

SEARCH_CONFIG: dict[str, dict[str, str]] = {
    "album":  {"entity": "album", "attribute": "albumTerm"},
    "song":   {"entity": "song",  "attribute": "songTerm"},
    "artist": {"entity": "album", "attribute": "artistTerm"},
}


def _extract_year(date_str: str) -> str:
    """Extract the year from an ISO date string like '2022-01-07T00:00:00Z'."""
    if not date_str:
        return "Unknown"
    try:
        normalized = date_str.replace("Z", "+00:00")
        return str(datetime.fromisoformat(normalized).year)
    except ValueError:
        match = re.match(r"^(\d{4})", date_str)
        if match:
            return match.group(1)
    return "Unknown"


def _sanitize_filename(name: str) -> str:
    """Remove or replace characters that are invalid in filenames."""
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", name)
    sanitized = sanitized.strip(". ")
    return sanitized or "artwork"


def replace_artwork_dimensions(url: str, dimensions: str) -> str:
    """Replace the image size token in an artwork URL while preserving its suffix."""
    artwork_url = url.strip()
    if not artwork_url:
        return ""
    prefix, separator, filename = artwork_url.rpartition("/")
    updated_filename = re.sub(r"\d+x\d+", dimensions, filename, count=1)
    if not separator:
        return updated_filename
    return f"{prefix}{separator}{updated_filename}"


def artwork_url_for_quality(
    preview_url: str, quality: ArtworkQuality | str = "high"
) -> str:
    """Build an artwork URL for the requested quality from the preview URL."""
    if quality not in ARTWORK_DIMENSIONS:
        raise ValueError(
            f"Invalid quality '{quality}'. Expected: {list(ARTWORK_DIMENSIONS)}"
        )
    return replace_artwork_dimensions(preview_url, ARTWORK_DIMENSIONS[quality])


def _build_artwork_url(preview_url: str) -> str:
    """Build a best-effort high-resolution artwork URL from the preview URL."""
    if not preview_url:
        return ""
    return artwork_url_for_quality(preview_url, "high")


def apply_quality_to_result(
    result: ArtworkResult, quality: ArtworkQuality | str
) -> ArtworkResult:
    """Return a copy of a result with its downloadable artwork URL rewritten."""
    return ArtworkResult(
        artist_name=result["artist_name"],
        collection_name=result["collection_name"],
        release_year=result["release_year"],
        artwork_link=artwork_url_for_quality(result["preview_url"], quality),
        preview_url=result["preview_url"],
    )


def apply_quality_to_results(
    results: list[ArtworkResult], quality: ArtworkQuality | str
) -> list[ArtworkResult]:
    """Return result copies with artwork links set to the requested quality."""
    return [apply_quality_to_result(result, quality) for result in results]


def _normalize_result(item: dict[str, object]) -> ArtworkResult | None:
    preview_url = str(item.get("artworkUrl100") or "").strip()
    if not preview_url:
        return None
    artist_name = str(item.get("artistName") or "Unknown Artist")
    collection_name = str(
        item.get("collectionName") or item.get("trackName") or "Unknown"
    )
    release_year = _extract_year(str(item.get("releaseDate") or ""))
    return ArtworkResult(
        artist_name=artist_name,
        collection_name=collection_name,
        release_year=release_year,
        artwork_link=_build_artwork_url(preview_url),
        preview_url=preview_url,
    )


def search_artwork(
    search_type: SearchType | str, name: str, limit: int = 200
) -> list[ArtworkResult]:
    """Search the iTunes API for album artwork.

    Args:
        search_type: One of 'album', 'song', or 'artist'.
        name: The search query string.
        limit: Maximum number of results (default 200, iTunes max).

    Returns:
        A list of dicts with keys: artist_name, collection_name,
        release_year, artwork_link, preview_url.

    Raises:
        ValueError: If search_type is not valid.
        ArtworkSearchError: If the API call fails or returns invalid JSON.
    """
    if search_type not in SEARCH_CONFIG:
        raise ValueError(
            f"Invalid search type '{search_type}'. Expected: {list(SEARCH_CONFIG)}"
        )
    query = name.strip()
    if not query:
        return []
    if limit < 1:
        raise ValueError("Search limit must be at least 1")
    limit = min(limit, 200)

    config = SEARCH_CONFIG[search_type]
    params = {
        "term": query,
        "entity": config["entity"],
        "attribute": config["attribute"],
        "limit": limit,
    }

    try:
        response = requests.get(BASE_URL, params=params, timeout=15)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise ArtworkSearchError(
            "Apple Music search timed out. Please try again."
        ) from exc
    except requests.RequestException as exc:
        raise ArtworkSearchError(
            "Unable to reach Apple Music right now. Please try again."
        ) from exc

    try:
        data = response.json()
    except ValueError as exc:
        raise ArtworkSearchError(
            "Apple Music returned an invalid response. Please try again."
        ) from exc

    raw_results = data.get("results", [])
    if not isinstance(raw_results, list):
        raise ArtworkSearchError("Apple Music returned an unexpected response format.")

    normalized_results = []
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        result = _normalize_result(item)
        if result is not None:
            normalized_results.append(result)
    return normalized_results


def fetch_preview_image(url: str, timeout: float = 10) -> PILImage.Image:
    """Fetch and decode a preview image for terminal display."""
    preview_url = url.strip()
    if not preview_url:
        raise ArtworkPreviewError("Missing preview image URL.")
    try:
        response = requests.get(preview_url, timeout=timeout)
        response.raise_for_status()
        return PILImage.open(io.BytesIO(response.content))
    except requests.Timeout as exc:
        raise ArtworkPreviewError("Preview image request timed out.") from exc
    except requests.RequestException as exc:
        raise ArtworkPreviewError("Unable to load preview image.") from exc
    except OSError as exc:
        raise ArtworkPreviewError("Preview image data could not be decoded.") from exc


def download_artwork(
    url: str, save_dir: Path, artist_name: str, collection_name: str
) -> Path:
    """Download artwork from a URL and save it to disk.

    Args:
        url: The full-resolution artwork URL.
        save_dir: Directory to save the file in.
        artist_name: Artist name for the filename.
        collection_name: Album/collection name for the filename.

    Returns:
        The Path to the saved file.

    Raises:
        ArtworkDownloadError: If the download or file save fails.
    """
    artwork_url = url.strip()
    if not artwork_url:
        raise ArtworkDownloadError("This result does not have a downloadable artwork URL.")

    filename = (
        f"{_sanitize_filename(collection_name)}_{_sanitize_filename(artist_name)}.jpg"
    )
    save_path = save_dir / filename
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise ArtworkDownloadError(
            f"Unable to create the save directory: {save_dir}"
        ) from exc

    try:
        response = requests.get(artwork_url, timeout=30, stream=True)
        response.raise_for_status()
    except requests.Timeout as exc:
        raise ArtworkDownloadError("Artwork download timed out. Please try again.") from exc
    except requests.RequestException as exc:
        raise ArtworkDownloadError(
            "Unable to download the selected artwork."
        ) from exc

    temp_path: Path | None = None
    try:
        with NamedTemporaryFile("wb", delete=False, dir=save_dir, suffix=".tmp") as temp_file:
            temp_path = Path(temp_file.name)
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    temp_file.write(chunk)
        temp_path.replace(save_path)
    except OSError as exc:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink(missing_ok=True)
        raise ArtworkDownloadError(
            f"Unable to save artwork to {save_dir}."
        ) from exc

    return save_path
