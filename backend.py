"""Backend module for PureArt — handles iTunes Search API calls and artwork downloads."""

import re
from pathlib import Path

import requests


BASE_URL = "https://itunes.apple.com/search"

SEARCH_CONFIG: dict[str, dict[str, str]] = {
    "album":  {"entity": "album", "attribute": "albumTerm"},
    "song":   {"entity": "song",  "attribute": "songTerm"},
    "artist": {"entity": "album", "attribute": "artistTerm"},
}


def _extract_year(date_str: str) -> str:
    """Extract the year from an ISO date string like '2022-01-07T00:00:00Z'."""
    if date_str and len(date_str) >= 4:
        return date_str[:4]
    return "Unknown"


def _sanitize_filename(name: str) -> str:
    """Remove or replace characters that are invalid in filenames."""
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", name)
    sanitized = sanitized.strip(". ")
    return sanitized or "artwork"


def search_artwork(search_type: str, name: str, limit: int = 200) -> list[dict[str, str]]:
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
        requests.RequestException: If the API call fails.
    """
    if search_type not in SEARCH_CONFIG:
        raise ValueError(
            f"Invalid search type '{search_type}'. Expected: {list(SEARCH_CONFIG)}"
        )

    config = SEARCH_CONFIG[search_type]
    params = {
        "term": name,
        "entity": config["entity"],
        "attribute": config["attribute"],
        "limit": limit,
    }

    response = requests.get(BASE_URL, params=params, timeout=15)
    response.raise_for_status()
    data = response.json()
    results = data.get("results", [])

    return [
        {
            "artist_name": item.get("artistName", "Unknown Artist"),
            "collection_name": item.get(
                "collectionName", item.get("trackName", "Unknown")
            ),
            "release_year": _extract_year(item.get("releaseDate", "")),
            "artwork_link": item.get("artworkUrl100", "").replace(
                "100x100bb", "10000x10000bb"
            ),
            "preview_url": item.get("artworkUrl100", ""),
        }
        for item in results
        if item.get("artworkUrl100")
    ]


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
        requests.RequestException: If the download fails.
    """
    filename = (
        f"{_sanitize_filename(collection_name)}_{_sanitize_filename(artist_name)}.jpg"
    )
    save_path = save_dir / filename
    save_dir.mkdir(parents=True, exist_ok=True)

    response = requests.get(url, timeout=30, stream=True)
    response.raise_for_status()

    with open(save_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return save_path