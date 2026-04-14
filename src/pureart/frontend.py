"""Frontend module for PureArt — TUI interface built with Textual and Rich."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import ClassVar

import pyfiglet
from PIL import Image as PILImage
from PIL import ImageOps
from rich.markup import escape
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.widget import Widget
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Input,
    Label,
    LoadingIndicator,
    Markdown,
    RadioButton,
    RadioSet,
    Static,
)

from pureart.backend import (
    ArtworkDownloadError,
    ArtworkQuality,
    ArtworkPreviewError,
    ArtworkResult,
    ArtworkSearchError,
    SearchType,
    apply_quality_to_results,
    download_artwork,
    fetch_preview_image,
    replace_artwork_dimensions,
    search_artwork,
)

# ─── Terminal image capability detection ──────────────────────────────
from textual_image.renderable import Image as _ResolvedRenderable
from textual_image.renderable.sixel import Image as _SixelImage
from textual_image.renderable.tgp import Image as _TGPImage
from textual_image.widget import Image as TerminalImage

SUPPORTS_NATIVE_IMAGES: bool = _ResolvedRenderable in (_SixelImage, _TGPImage)

# ─── Constants ────────────────────────────────────────────────────────
RESULTS_PER_PAGE = 10
FILTER_PLACEHOLDERS = {
    "album": "Filter by artist or year...",
    "artist": "Filter by album or year...",
    "song": "Filter by artist, album, or year...",
}
QUALITY_LABELS: dict[ArtworkQuality, str] = {
    "low": "Low (600x600 px)",
    "medium": "Medium (1280x1280 px)",
    "high": "High (best available)",
}

# ─── Home Screen ─────────────────────────────────────────────────────


class HomeScreen(Screen):
    """Main menu: logo, search-type selector, and input."""

    OPTIONS: ClassVar[dict[str, str]] = {
        "album": "Album",
        "artist": "Artist",
        "song": "Song",
    }
    DEFAULT_SEARCH_TYPE: ClassVar[SearchType] = "album"
    DEFAULT_QUALITY: ClassVar[ArtworkQuality] = "high"

    BINDINGS = [
        Binding("1", "select_category('album')", "Album"),
        Binding("2", "select_category('artist')", "Artist"),
        Binding("3", "select_category('song')", "Song"),
        Binding("ctrl+r", "submit_search", "Search"),
        Binding("tab", "focus_next", "Next"),
        Binding("shift+tab", "focus_previous", "Previous"),
    ]

    welcome_text = """TUI app to download album art

## How to use

1. Select to search for an album name, artist name, or song name.
2. Choose the download quality you want.
3. Search for the respective name.
4. Scroll through the options and download the one you want.
5. Enjoy!

## Disclaimer

- Not every terminal supports inline image viewing.
- If your terminal app supports it, a preview of the album art will be automatically visible.
- If not, you can manually click on each link for a preview of each album cover and download the one you want.
"""

    # Cache the logo so pyfiglet only runs once
    _logo_cache: ClassVar[Text | None] = None

    @classmethod
    def _get_logo(cls) -> Text:
        if cls._logo_cache is None:
            logo = pyfiglet.figlet_format("PureArt", font="isometric1", width=200)
            text = Text(logo)
            length = len(logo)
            text.stylize("bold #FF6B6B", 0, length // 3)
            text.stylize("bold #FF8E53", length // 3, length * 2 // 3)
            text.stylize("bold #FFC300", length * 2 // 3, length)
            cls._logo_cache = text
        return cls._logo_cache

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._pending_quality: ArtworkQuality = self.DEFAULT_QUALITY

    def compose(self) -> ComposeResult:
        with Vertical(id="home-shell"):
            with Vertical(id="hero-panel", classes="home-panel"):
                yield Static(self._get_logo(), id="logo")
            with Horizontal(id="main-layout"):
                with Vertical(id="info-panel", classes="home-panel"):
                    yield Static("Welcome to PureArt", classes="panel-title")
                    yield Markdown(self.welcome_text, id="welcome")
                with VerticalScroll(id="control-column"):
                    with Horizontal(id="selection-row"):
                        with Vertical(id="selector-panel", classes="home-panel"):
                            yield Static("Search by", classes="panel-title")
                            with RadioSet(id="search-type-set", compact=True):
                                yield RadioButton(
                                    self.OPTIONS["album"],
                                    id="search-album",
                                    value=True,
                                )
                                yield RadioButton(
                                    self.OPTIONS["artist"], id="search-artist"
                                )
                                yield RadioButton(self.OPTIONS["song"], id="search-song")
                        with Vertical(id="quality-panel", classes="home-panel"):
                            yield Static("Download quality", classes="panel-title")
                            with RadioSet(id="quality-set", compact=True):
                                yield RadioButton(
                                    QUALITY_LABELS["low"],
                                    id="quality-low",
                                    value=True,
                                )
                                yield RadioButton(
                                    QUALITY_LABELS["medium"], id="quality-medium"
                                )
                                yield RadioButton(
                                    QUALITY_LABELS["high"], id="quality-high"
                                )
                    with Vertical(id="query-panel", classes="home-panel"):
                        yield Static("Search", classes="panel-title")
                        yield Input(placeholder="Search...", id="search-input")
                        yield Static(id="search-status")
                        yield LoadingIndicator(id="loading-indicator")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search-status", Static).display = False
        self.query_one("#loading-indicator", LoadingIndicator).display = False
        self._set_selected_category(self.DEFAULT_SEARCH_TYPE)
        self.query_one("#search-type-set", RadioSet).focus()
        self._refresh_footer_bindings()

    # ── Selection handling ────────────────────────────────────────────

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id == "search-type-set":
            pressed_id = event.pressed.id or ""
            category = pressed_id.removeprefix("search-")
            self._set_selected_category(category if category in self.OPTIONS else None)
            return
        if event.radio_set.id == "quality-set":
            self._refresh_footer_bindings()

    def _set_selected_category(self, category: str | None) -> None:
        if category in self.OPTIONS:
            self.query_one("#search-input", Input).placeholder = (
                f"Search {self.OPTIONS[category]}..."
            )
        else:
            self.query_one("#search-input", Input).placeholder = "Search..."
        self._refresh_footer_bindings()

    # ── Search handling ───────────────────────────────────────────────

    def _get_selected_type(self) -> SearchType | None:
        radio_set = self.query_one("#search-type-set", RadioSet)
        pressed = radio_set.pressed_button
        if pressed is None or pressed.id is None:
            return None
        category = pressed.id.removeprefix("search-")
        if category in self.OPTIONS:
            return category
        return None

    def _get_selected_quality(self) -> ArtworkQuality:
        radio_set = self.query_one("#quality-set", RadioSet)
        pressed = radio_set.pressed_button
        if pressed is None or pressed.id is None:
            return self.DEFAULT_QUALITY
        quality = pressed.id.removeprefix("quality-")
        if quality in QUALITY_LABELS:
            return quality
        return self.DEFAULT_QUALITY

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._start_search(event.value)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search-input":
            self._refresh_footer_bindings()

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action == "submit_search":
            search_type = self._get_selected_type()
            input_widget = self.query_one("#search-input", Input)
            query = input_widget.value.strip()
            return True if (search_type and query and input_widget.display) else False
        return True

    def action_select_category(self, category: str) -> None:
        if category not in self.OPTIONS:
            return
        self.query_one(f"#search-{category}", RadioButton).value = True
        self._set_selected_category(category)
        self.query_one("#search-type-set", RadioSet).focus()
        self._refresh_footer_bindings()

    def action_submit_search(self) -> None:
        input_widget = self.query_one("#search-input", Input)
        self._start_search(input_widget.value)

    def action_focus_next(self) -> None:
        self.app.action_focus_next()
        self._refresh_footer_bindings()

    def action_focus_previous(self) -> None:
        self.app.action_focus_previous()
        self._refresh_footer_bindings()

    def _start_search(self, value: str) -> None:
        search_type = self._get_selected_type()
        if not search_type:
            self.notify("Please select a search category first", severity="warning")
            return
        quality = self._get_selected_quality()
        self._pending_quality = quality
        query = value.strip()
        if not query:
            self.notify("Please enter a search term", severity="warning")
            return

        self._set_loading(query)
        self._perform_search(search_type, query)

    def _set_loading(self, query: str | None = None) -> None:
        is_loading = query is not None
        self.query_one("#search-input", Input).display = not is_loading

        status = self.query_one("#search-status", Static)
        status.display = is_loading
        if query:
            status.update(f"Searching for '{query}'...")

        self.query_one("#loading-indicator", LoadingIndicator).display = is_loading
        self._refresh_footer_bindings()

    @work(thread=True, exclusive=True)
    def _perform_search(self, search_type: str, query: str) -> None:
        try:
            results = search_artwork(search_type, query)
            self.app.call_from_thread(
                self._on_search_complete, search_type, query, results
            )
        except (ArtworkSearchError, ValueError) as exc:
            self.app.call_from_thread(self._on_search_error, str(exc))
        except Exception:
            self.app.call_from_thread(
                self._on_search_error,
                "Something unexpected went wrong while searching.",
            )

    def _on_search_complete(
        self,
        search_type: str,
        query: str,
        results: list[ArtworkResult],
    ) -> None:
        self._set_loading(None)
        if not results:
            self.notify(f"No results found for '{query}'", severity="warning")
            return
        quality = self._pending_quality
        quality_results = apply_quality_to_results(results, quality)
        self.app.push_screen(
            ResultsScreen(search_type, query, quality, quality_results)
        )

    def _on_search_error(self, error_msg: str) -> None:
        self._set_loading(None)
        self.notify(f"Search failed: {error_msg}", severity="error")

    def _refresh_footer_bindings(self) -> None:
        if self.is_mounted:
            self.query_one(Footer).refresh_bindings()


# ─── Result Card ─────────────────────────────────────────────────────


class ResultCard(Widget, can_focus=True):
    """A single result card with album info and a Download button."""

    BINDINGS = [
        Binding("enter", "download", "Download"),
    ]

    class DownloadRequested(Message):
        """Posted when the user clicks Download on this card."""

        def __init__(self, result: ArtworkResult) -> None:
            super().__init__()
            self.result = result

    def __init__(
        self,
        result: ArtworkResult,
        card_index: int,
        preview_image: PILImage.Image | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.result = result
        self.card_index = card_index
        self.preview_image = preview_image

    def compose(self) -> ComposeResult:
        title = escape(self.result["collection_name"])
        artist = escape(self.result["artist_name"])
        year = escape(self.result["release_year"])
        with Vertical(classes="result-card"):
            if SUPPORTS_NATIVE_IMAGES:
                with Horizontal(classes="result-card-image-row"):
                    yield TerminalImage(
                        None,
                        id=f"img-{self.card_index}",
                        classes="result-card-image",
                    )
            yield Label(
                f"[bold]{title}[/bold]",
                classes="result-card-title",
            )
            yield Label(artist, classes="result-card-artist")
            yield Label(year, classes="result-card-year")

            if not SUPPORTS_NATIVE_IMAGES:
                link = self.result.get("artwork_link", "").replace("'", "\\'")
                yield Label(
                    f"[@click=app.open_url('{link}')]→ Open selected artwork[/]",
                    classes="result-card-link",
                )

            yield Button(
                "↓ Download",
                id=f"dl-{self.card_index}",
                classes="download-btn",
            )

    def on_mount(self) -> None:
        if SUPPORTS_NATIVE_IMAGES and self.preview_image is not None:
            self._set_preview(self.preview_image)

    def set_preview_image(self, img: PILImage.Image) -> None:
        self.preview_image = img
        if self.is_mounted:
            self._set_preview(img)

    def _set_preview(self, img: PILImage.Image) -> None:
        try:
            self.query_one(f"#img-{self.card_index}", TerminalImage).image = img
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.post_message(self.DownloadRequested(self.result))

    def action_download(self) -> None:
        self.post_message(self.DownloadRequested(self.result))


class VisibleDirectoryTree(DirectoryTree):
    """Directory tree that hides dotfiles and dot-directories."""

    def filter_paths(self, paths: Iterable[Path]) -> Iterable[Path]:
        return [path for path in paths if not path.name.startswith(".")]


# ─── Save Screen (Modal) ─────────────────────────────────────────────


class SaveScreen(ModalScreen[Path | None]):
    """Modal directory picker for choosing where to save artwork."""

    BINDINGS = [
        Binding("ctrl+s", "confirm_save", "Save Here"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._selected_path: Path = Path.home() / "Downloads"

    def compose(self) -> ComposeResult:
        with Vertical(id="save-dialog"):
            yield Label("[bold]Save artwork to:[/bold]", id="save-title")
            yield VisibleDirectoryTree(str(Path.home()), id="save-tree")
            yield Label(
                f"Selected: {self._selected_path}", id="selected-path-label"
            )
            with Horizontal(id="save-buttons"):
                yield Button("Save Here", variant="primary", id="save-confirm")
                yield Button("Cancel", variant="default", id="save-cancel")
            yield Footer()

    def on_mount(self) -> None:
        self.query_one("#save-tree", VisibleDirectoryTree).focus()
        self.query_one(Footer).refresh_bindings()

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self._selected_path = Path(event.path)
        self.query_one("#selected-path-label", Label).update(
            f"Selected: {self._selected_path}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-confirm":
            self.action_confirm_save()
        elif event.button.id == "save-cancel":
            self.dismiss(None)

    def action_confirm_save(self) -> None:
        self.dismiss(self._selected_path)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ─── Results Screen ──────────────────────────────────────────────────


class ResultsScreen(Screen):
    """Paginated search results with client-side filtering."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("left", "prev_page", "Previous page"),
        Binding("right", "next_page", "Next page"),
        Binding("/", "focus_filter", "Filter"),
        Binding("tab", "focus_next", "Next"),
        Binding("shift+tab", "focus_previous", "Previous"),
    ]

    current_page: reactive[int] = reactive(0)

    def __init__(
        self,
        search_type: str,
        query: str,
        quality: ArtworkQuality,
        results: list[ArtworkResult],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.search_type = search_type
        self.query_text = query
        self.download_quality = quality
        self.all_results = results
        self.filtered_results: list[ArtworkResult] = list(results)
        self.preview_cache: dict[str, PILImage.Image] = {}
        self._pending_previews: set[str] = set()
        self._card_order: list[ResultCard] = []
        self._visible_cards: dict[str, ResultCard] = {}

    def compose(self) -> ComposeResult:
        yield Static(self._results_header_text(), id="results-header")
        yield Input(
            placeholder=FILTER_PLACEHOLDERS.get(
                self.search_type, "Filter results..."
            ),
            id="filter-input",
        )
        yield VerticalScroll(id="results-container")
        with Horizontal(id="pagination-bar"):
            yield Button("◀ Previous", id="prev-btn", classes="pagination-btn")
            yield Label("Page 1 of 1", id="page-indicator")
            yield Button("Next ▶", id="next-btn", classes="pagination-btn")
        yield Footer()

    def on_mount(self) -> None:
        self._render_page()
        self._refresh_footer_bindings()

    def _results_header_text(self) -> str:
        escaped_query = escape(self.query_text)
        quality_label = escape(
            QUALITY_LABELS.get(self.download_quality, QUALITY_LABELS["high"])
        )
        counts = (
            f"{len(self.filtered_results)} of {len(self.all_results)} results"
            if self.filtered_results != self.all_results
            else f"{len(self.all_results)} results"
        )
        return (
            f"[bold]Results for[/bold] [italic #FFE500]'{escaped_query}'[/italic #FFE500] "
            f"[dim]({counts} • {quality_label} downloads)[/dim]"
        )

    # ── Pagination ────────────────────────────────────────────────────

    @property
    def total_pages(self) -> int:
        return max(
            1, (len(self.filtered_results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
        )

    def watch_current_page(self, _page: int) -> None:
        if self.is_mounted:
            self._render_page()
            self._refresh_footer_bindings()

    def _render_page(self) -> None:
        container = self.query_one("#results-container", VerticalScroll)
        container.remove_children()
        self._card_order.clear()
        self._visible_cards.clear()

        start = self.current_page * RESULTS_PER_PAGE
        end = start + RESULTS_PER_PAGE
        page_results = self.filtered_results[start:end]

        if page_results:
            cards: list[ResultCard] = []
            for i, result in enumerate(page_results):
                preview_url = self._get_preview_source(result)
                preview_image = self.preview_cache.get(preview_url)
                card = ResultCard(result, start + i, preview_image=preview_image)
                cards.append(card)
                self._card_order.append(card)
                self._visible_cards[preview_url] = card
            grid = Grid(*cards, classes="results-grid")
            grid.styles.grid_size_columns = 1 if self.size.width < 120 else 2
            container.mount(grid)
            if SUPPORTS_NATIVE_IMAGES:
                for result in page_results:
                    preview_url = self._get_preview_source(result)
                    if (
                        preview_url
                        and preview_url not in self.preview_cache
                        and preview_url not in self._pending_previews
                    ):
                        self._pending_previews.add(preview_url)
                        self._load_preview(preview_url)
        else:
            empty_message = (
                "No matching results found."
                if self.filtered_results != self.all_results
                else "No results available."
            )
            container.mount(Static(empty_message, classes="empty-results"))

        # Update pagination UI
        self.query_one("#page-indicator", Label).update(
            f"Page {self.current_page + 1} of {self.total_pages}"
        )
        self.query_one("#prev-btn", Button).disabled = self.current_page <= 0
        self.query_one("#next-btn", Button).disabled = (
            self.current_page >= self.total_pages - 1
        )
        self._refresh_footer_bindings()

    def on_resize(self) -> None:
        if self.is_mounted:
            self._render_page()

    # ── Filtering ─────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "filter-input":
            self._apply_filter(event.value)

    def _apply_filter(self, filter_text: str) -> None:
        query = filter_text.strip().lower()
        if not query:
            self.filtered_results = list(self.all_results)
        else:
            self.filtered_results = [
                r
                for r in self.all_results
                if query in r.get("artist_name", "").lower()
                or query in r.get("collection_name", "").lower()
                or query in r.get("release_year", "").lower()
            ]
        if self.current_page != 0:
            self.current_page = 0
        else:
            self._render_page()
        self.query_one("#results-header", Static).update(self._results_header_text())
        self._refresh_footer_bindings()

    # ── Download ──────────────────────────────────────────────────────

    def on_result_card_download_requested(
        self, event: ResultCard.DownloadRequested
    ) -> None:
        self._initiate_download(event.result)

    def _initiate_download(self, result: ArtworkResult) -> None:
        def on_save_path(path: Path | None) -> None:
            if path is not None:
                self._download_to_path(result, path)

        self.app.push_screen(SaveScreen(), callback=on_save_path)

    @work(thread=True)
    def _download_to_path(self, result: ArtworkResult, save_dir: Path) -> None:
        try:
            saved = download_artwork(
                url=result["artwork_link"],
                save_dir=save_dir,
                artist_name=result["artist_name"],
                collection_name=result["collection_name"],
            )
            self.app.call_from_thread(
                self.notify,
                f"✓ Downloaded ({self.download_quality}): {saved.name}",
                severity="information",
            )
        except ArtworkDownloadError as exc:
            self.app.call_from_thread(
                self.notify, f"Download failed: {exc}", severity="error"
            )
        except Exception:
            self.app.call_from_thread(
                self.notify,
                "Download failed: Something unexpected went wrong.",
                severity="error",
            )

    @work(thread=True)
    def _load_preview(self, preview_url: str) -> None:
        try:
            image = fetch_preview_image(preview_url)
            image = ImageOps.contain(image.convert("RGB"), (768, 768))
            self.app.call_from_thread(self._cache_and_apply_preview, preview_url, image)
        except ArtworkPreviewError:
            fallback_url = self._get_preview_fallback(preview_url)
            if fallback_url and fallback_url != preview_url:
                try:
                    image = fetch_preview_image(fallback_url)
                    image = ImageOps.contain(image.convert("RGB"), (768, 768))
                    self.app.call_from_thread(
                        self._cache_and_apply_preview, preview_url, image
                    )
                    return
                except ArtworkPreviewError:
                    pass
            self.app.call_from_thread(self._mark_preview_complete, preview_url)

    def _cache_and_apply_preview(
        self, preview_url: str, image: PILImage.Image
    ) -> None:
        self._pending_previews.discard(preview_url)
        self.preview_cache[preview_url] = image
        card = self._visible_cards.get(preview_url)
        if card is not None:
            card.set_preview_image(image)

    def _mark_preview_complete(self, preview_url: str) -> None:
        self._pending_previews.discard(preview_url)

    def _get_preview_source(self, result: ArtworkResult) -> str:
        preview_url = result.get("preview_url", "")
        return replace_artwork_dimensions(preview_url, "300x300")

    def _get_preview_fallback(self, preview_url: str) -> str:
        return replace_artwork_dimensions(preview_url, "100x100")

    # ── Navigation ────────────────────────────────────────────────────

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool | None:
        if action in {"prev_page", "next_page"}:
            if self.total_pages <= 1:
                return False
            if action == "prev_page":
                return None if self.current_page <= 0 else True
            return None if self.current_page >= self.total_pages - 1 else True
        return True

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "prev-btn":
            self.action_prev_page()
        elif event.button.id == "next-btn":
            self.action_next_page()

    def action_focus_filter(self) -> None:
        self.query_one("#filter-input", Input).focus()
        self._refresh_footer_bindings()

    def action_focus_next(self) -> None:
        if not self._card_order:
            self.app.action_focus_next()
            self._refresh_footer_bindings()
            return

        current_card = self._get_focused_card()
        if current_card is None or current_card not in self._card_order:
            self._card_order[0].focus()
        else:
            current_index = self._card_order.index(current_card)
            next_index = (current_index + 1) % len(self._card_order)
            self._card_order[next_index].focus()
        self._refresh_footer_bindings()

    def action_focus_previous(self) -> None:
        if not self._card_order:
            self.app.action_focus_previous()
            self._refresh_footer_bindings()
            return

        current_card = self._get_focused_card()
        if current_card is None or current_card not in self._card_order:
            self._card_order[-1].focus()
        else:
            current_index = self._card_order.index(current_card)
            previous_index = (current_index - 1) % len(self._card_order)
            self._card_order[previous_index].focus()
        self._refresh_footer_bindings()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_prev_page(self) -> None:
        if self.current_page > 0:
            self.current_page -= 1

    def action_next_page(self) -> None:
        if self.current_page < self.total_pages - 1:
            self.current_page += 1

    def _get_focused_card(self) -> ResultCard | None:
        focused = self.app.focused
        while focused is not None:
            if isinstance(focused, ResultCard):
                return focused
            focused = focused.parent
        return None

    def _refresh_footer_bindings(self) -> None:
        if self.is_mounted:
            self.query_one(Footer).refresh_bindings()


# ─── App ──────────────────────────────────────────────────────────────


class PureArt(App):
    """PureArt — Album Art Downloader TUI."""

    TITLE = "PureArt"
    CSS_PATH = Path(__file__).parent / "styles.tcss"
    SCREENS = {"home": HomeScreen}
    BINDINGS = [Binding("ctrl+q", "quit", "Quit")]

    def on_mount(self) -> None:
        self.push_screen("home")

    def action_toggle_dark(self) -> None:
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )


if __name__ == "__main__":
    app = PureArt()
    app.run()
