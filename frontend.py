"""Frontend module for PureArt — TUI interface built with Textual and Rich."""

from __future__ import annotations

import io
from pathlib import Path
from typing import ClassVar

import pyfiglet
import requests as req_lib
from PIL import Image as PILImage
from rich.text import Text
from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Grid, Horizontal, Vertical, VerticalScroll
from textual.message import Message
from textual.reactive import reactive
from textual.screen import ModalScreen, Screen
from textual.timer import Timer
from textual.widget import Widget
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Input,
    Label,
    ListItem,
    ListView,
    LoadingIndicator,
    Static,
)

from backend import download_artwork, search_artwork

# ─── Terminal image capability detection ──────────────────────────────
from textual_image.renderable import Image as _ResolvedRenderable
from textual_image.renderable.sixel import Image as _SixelImage
from textual_image.renderable.tgp import Image as _TGPImage
from textual_image.widget import Image as TerminalImage

SUPPORTS_NATIVE_IMAGES: bool = _ResolvedRenderable in (_SixelImage, _TGPImage)

# ─── Constants ────────────────────────────────────────────────────────
CONNECTOR_ARROW = "────────────────▶"
GRADIENT_COLORS = [
    "#FF6B6B", "#FF7560", "#FF7E55", "#FF884A", "#FF8E53",
    "#FF9A4A", "#FFA641", "#FFB238", "#FFBA30", "#FFC300",
]
RESULTS_PER_PAGE = 10
FILTER_PLACEHOLDERS = {
    "album": "Filter by artist or year...",
    "artist": "Filter by album or year...",
    "song": "Filter by artist, album, or year...",
}


# ─── Animated Connector ──────────────────────────────────────────────


class AnimatedConnector(Widget):
    """Horizontal arrow with a flowing color-wave animation."""

    position: reactive[int] = reactive(0)
    connector_visible: reactive[bool] = reactive(True)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._frame: int = 0
        self._timer: Timer | None = None

    def on_mount(self) -> None:
        self._timer = self.set_interval(0.15, self._advance_frame)

    def _advance_frame(self) -> None:
        self._frame += 1
        self.refresh()

    def render(self) -> Text:
        if not self.connector_visible:
            return Text("")

        # Build the animated arrow line
        arrow = Text()
        for i, char in enumerate(CONNECTOR_ARROW):
            color_idx = (i + self._frame) % len(GRADIENT_COLORS)
            arrow.append(char, style=f"bold {GRADIENT_COLORS[color_idx]}")

        # Position arrow to align with the highlighted ListItem.
        # ListView internals: border(1) + padding(1) + item_index * item_height(3)
        # + center of item(1) = position * 3 + 3.  Adjusted for the connector
        # widget sitting alongside the Vertical that wraps the ListView.
        center_row = self.position * 3 + 2
        total_rows = 11  # Matches ListView visible height

        result = Text()
        blank = " " * len(CONNECTOR_ARROW)
        for row in range(total_rows):
            if row == center_row:
                result.append(arrow)
            else:
                result.append(blank)
            if row < total_rows - 1:
                result.append("\n")
        return result


# ─── Home Screen ─────────────────────────────────────────────────────


class HomeScreen(Screen):
    """Main menu: logo, search-type selector, animated connector, input."""

    OPTIONS: ClassVar[dict[str, str]] = {
        "album": "Album",
        "artist": "Artist",
        "song": "Song",
    }

    BINDINGS = [
        Binding("escape", "app.quit", "Quit", show=False),
    ]

    welcome_text = """
        [bold]TUI app to download album art[/bold]

        [underline]How to use:[/underline]
            1. Select to search for an album name, artist name, or song name
            2. Search for the respective name
            3. Scroll through the options and download the one you want
            4. Enjoy!

        [underline]Disclaimer:[/underline]
            * Not every terminal supports inline image viewing
            * If your terminal app supports it, a preview of the album art will be automatically visible
            * If not, you can manually click on each link for a preview of each album cover and download the one you want
        """

    # Cache the logo so pyfiglet only runs once
    _logo_cache: ClassVar[Text | None] = None

    @classmethod
    def _get_logo(cls) -> Text:
        if cls._logo_cache is None:
            logo = pyfiglet.figlet_format("PureArt", font="larry3d", width=200)
            text = Text(logo)
            length = len(logo)
            text.stylize("bold #FF6B6B", 0, length // 3)
            text.stylize("bold #FF8E53", length // 3, length * 2 // 3)
            text.stylize("bold #FFC300", length * 2 // 3, length)
            cls._logo_cache = text
        return cls._logo_cache

    def compose(self) -> ComposeResult:
        yield Static(self._get_logo(), id="logo")
        yield Static(self.welcome_text, id="welcome")
        with Horizontal(id="main-layout"):
            with Vertical(id="left-column"):
                yield ListView(
                    ListItem(Label("  Album"), id="album"),
                    ListItem(Label("  Artist"), id="artist"),
                    ListItem(Label("  Song"), id="song"),
                )
            yield AnimatedConnector(id="connector")
            with Vertical(id="right-column"):
                yield Input(placeholder="Search...", id="search-input")
                yield Static(id="search-status")
                yield LoadingIndicator(id="loading-indicator")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search-status", Static).display = False
        self.query_one("#loading-indicator", LoadingIndicator).display = False

    # ── Selection handling ────────────────────────────────────────────

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        for item_id, label_text in self.OPTIONS.items():
            item = self.query_one(f"#{item_id}", ListItem)
            item.query_one(Label).update(f"  {label_text}")
            item.remove_class("selected-item")

        connector = self.query_one("#connector", AnimatedConnector)
        if event.item and event.item.id in self.OPTIONS:
            event.item.query_one(Label).update(
                f"* {self.OPTIONS[event.item.id]}"
            )
            event.item.add_class("selected-item")
            self.query_one("#search-input", Input).placeholder = (
                f"Search {self.OPTIONS[event.item.id]}..."
            )
            keys = list(self.OPTIONS.keys())
            connector.position = keys.index(event.item.id)
            connector.connector_visible = True
        else:
            connector.connector_visible = False

    # ── Search handling ───────────────────────────────────────────────

    def _get_selected_type(self) -> str | None:
        for item_id in self.OPTIONS:
            item = self.query_one(f"#{item_id}", ListItem)
            if "selected-item" in item.classes:
                return item_id
        return None

    def on_input_submitted(self, event: Input.Submitted) -> None:
        search_type = self._get_selected_type()
        if not search_type:
            self.notify("Please select a search category first", severity="warning")
            return
        query = event.value.strip()
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

    @work(thread=True, exclusive=True)
    def _perform_search(self, search_type: str, query: str) -> None:
        try:
            results = search_artwork(search_type, query)
            self.app.call_from_thread(
                self._on_search_complete, search_type, query, results
            )
        except Exception as exc:
            self.app.call_from_thread(self._on_search_error, str(exc))

    def _on_search_complete(
        self,
        search_type: str,
        query: str,
        results: list[dict[str, str]],
    ) -> None:
        self._set_loading(None)
        if not results:
            self.notify(f"No results found for '{query}'", severity="warning")
            return
        self.app.push_screen(ResultsScreen(search_type, query, results))

    def _on_search_error(self, error_msg: str) -> None:
        self._set_loading(None)
        self.notify(f"Search failed: {error_msg}", severity="error")


# ─── Result Card ─────────────────────────────────────────────────────


class ResultCard(Widget):
    """A single result card with album info and a Download button."""

    class DownloadRequested(Message):
        """Posted when the user clicks Download on this card."""

        def __init__(self, result: dict[str, str]) -> None:
            super().__init__()
            self.result = result

    def __init__(self, result: dict[str, str], card_index: int, **kwargs) -> None:
        super().__init__(**kwargs)
        self.result = result
        self.card_index = card_index

    def compose(self) -> ComposeResult:
        with Vertical(classes="result-card"):
            if SUPPORTS_NATIVE_IMAGES:
                yield TerminalImage(None, id=f"img-{self.card_index}",
                                    classes="result-card-image")
            yield Label(
                f"[bold]{self.result['collection_name']}[/bold]",
                classes="result-card-title",
            )
            yield Label(self.result["artist_name"], classes="result-card-artist")
            yield Label(self.result["release_year"], classes="result-card-year")

            if not SUPPORTS_NATIVE_IMAGES:
                link = self.result.get("artwork_link", "")
                yield Label(
                    f"[@click=app.open_link('{link}')]→ View full resolution[/]",
                    classes="result-card-link",
                )

            yield Button(
                "↓ Download",
                id=f"dl-{self.card_index}",
                classes="download-btn",
            )

    def on_mount(self) -> None:
        if SUPPORTS_NATIVE_IMAGES and self.result.get("preview_url"):
            self._load_preview()

    @work(thread=True)
    def _load_preview(self) -> None:
        """Download the 100×100 thumbnail and set it on the image widget."""
        try:
            resp = req_lib.get(self.result["preview_url"], timeout=10)
            resp.raise_for_status()
            img = PILImage.open(io.BytesIO(resp.content))
            self.app.call_from_thread(self._set_preview, img)
        except Exception:
            pass  # Fail silently — card still shows text info

    def _set_preview(self, img: PILImage.Image) -> None:
        try:
            self.query_one(f"#img-{self.card_index}", TerminalImage).image = img
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.post_message(self.DownloadRequested(self.result))


# ─── Save Screen (Modal) ─────────────────────────────────────────────


class SaveScreen(ModalScreen[Path | None]):
    """Modal directory picker for choosing where to save artwork."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self._selected_path: Path = Path.home() / "Downloads"

    def compose(self) -> ComposeResult:
        with Vertical(id="save-dialog"):
            yield Label("[bold]Save artwork to:[/bold]", id="save-title")
            yield DirectoryTree(str(Path.home()), id="save-tree")
            yield Label(
                f"Selected: {self._selected_path}", id="selected-path-label"
            )
            with Horizontal(id="save-buttons"):
                yield Button("Save Here", variant="primary", id="save-confirm")
                yield Button("Cancel", variant="default", id="save-cancel")

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self._selected_path = Path(event.path)
        self.query_one("#selected-path-label", Label).update(
            f"Selected: {self._selected_path}"
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save-confirm":
            self.dismiss(self._selected_path)
        elif event.button.id == "save-cancel":
            self.dismiss(None)

    def action_cancel(self) -> None:
        self.dismiss(None)


# ─── Results Screen ──────────────────────────────────────────────────


class ResultsScreen(Screen):
    """Paginated search results with client-side filtering."""

    BINDINGS = [
        Binding("escape", "go_back", "Back"),
        Binding("left", "prev_page", "Previous page", show=False),
        Binding("right", "next_page", "Next page", show=False),
    ]

    current_page: reactive[int] = reactive(0)

    def __init__(
        self,
        search_type: str,
        query: str,
        results: list[dict[str, str]],
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.search_type = search_type
        self.query_text = query
        self.all_results = results
        self.filtered_results: list[dict[str, str]] = list(results)

    def compose(self) -> ComposeResult:
        yield Static(
            f"[bold]Results for[/bold] [italic #FF8E53]'{self.query_text}'[/italic #FF8E53] "
            f"[dim]({len(self.all_results)} results)[/dim]",
            id="results-header",
        )
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

    # ── Pagination ────────────────────────────────────────────────────

    @property
    def total_pages(self) -> int:
        return max(
            1, (len(self.filtered_results) + RESULTS_PER_PAGE - 1) // RESULTS_PER_PAGE
        )

    def watch_current_page(self, _page: int) -> None:
        if self.is_mounted:
            self._render_page()

    def _render_page(self) -> None:
        container = self.query_one("#results-container", VerticalScroll)
        container.remove_children()

        start = self.current_page * RESULTS_PER_PAGE
        end = start + RESULTS_PER_PAGE
        page_results = self.filtered_results[start:end]

        # Mount all cards within a single styled Grid
        cards = [ResultCard(r, start + i) for i, r in enumerate(page_results)]
        if cards:
            container.mount(Grid(*cards, id="results-grid"))

        # Update pagination UI
        self.query_one("#page-indicator", Label).update(
            f"Page {self.current_page + 1} of {self.total_pages}"
        )
        self.query_one("#prev-btn", Button).disabled = self.current_page <= 0
        self.query_one("#next-btn", Button).disabled = (
            self.current_page >= self.total_pages - 1
        )

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
        self.current_page = 0
        self._render_page()
        self.query_one("#results-header", Static).update(
            f"[bold]Results for[/bold] [italic #FF8E53]'{self.query_text}'[/italic #FF8E53] "
            f"[dim]({len(self.filtered_results)} of {len(self.all_results)} results)[/dim]"
        )

    # ── Download ──────────────────────────────────────────────────────

    def on_result_card_download_requested(
        self, event: ResultCard.DownloadRequested
    ) -> None:
        self._initiate_download(event.result)

    def _initiate_download(self, result: dict[str, str]) -> None:
        def on_save_path(path: Path | None) -> None:
            if path is not None:
                self._download_to_path(result, path)

        self.app.push_screen(SaveScreen(), callback=on_save_path)

    @work(thread=True)
    def _download_to_path(self, result: dict[str, str], save_dir: Path) -> None:
        try:
            saved = download_artwork(
                url=result["artwork_link"],
                save_dir=save_dir,
                artist_name=result["artist_name"],
                collection_name=result["collection_name"],
            )
            self.app.call_from_thread(
                self.notify, f"✓ Downloaded: {saved.name}", severity="information"
            )
        except Exception as exc:
            self.app.call_from_thread(
                self.notify, f"Download failed: {exc}", severity="error"
            )

    # ── Navigation ────────────────────────────────────────────────────

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "prev-btn":
            self.action_prev_page()
        elif event.button.id == "next-btn":
            self.action_next_page()

    def action_go_back(self) -> None:
        self.app.pop_screen()

    def action_prev_page(self) -> None:
        if self.current_page > 0:
            self.current_page -= 1

    def action_next_page(self) -> None:
        if self.current_page < self.total_pages - 1:
            self.current_page += 1


# ─── App ──────────────────────────────────────────────────────────────


class PureArt(App):
    """PureArt — Album Art Downloader TUI."""

    TITLE = "PureArt"
    CSS_PATH = "styles.tcss"
    SCREENS = {"home": HomeScreen}
    BINDINGS = [
        Binding("d", "toggle_dark", "Toggle dark mode"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def on_mount(self) -> None:
        self.push_screen("home")

    def action_toggle_dark(self) -> None:
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )


if __name__ == "__main__":
    app = PureArt()
    app.run()