"""Reviewed native KOReader extensions and their pinned release layouts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class CatalogueEntry:
    id: str
    name: str
    plugin_id: str
    repository: str
    version: str
    tag: str
    asset: str
    category: str
    summary: str
    description: str
    instructions: str
    minimum: str = ""


# Release assets and their installation layouts were reviewed together. Refreshing
# GitHub metadata never substitutes an unreviewed release for one of these pins.
CATALOGUE = (
    CatalogueEntry(
        id="simpleui",
        name="SimpleUI",
        plugin_id="simpleui.koplugin",
        repository="doctorhetfield-cmd/simpleui.koplugin",
        version="2.7.1",
        tag="2.7.1",
        asset="simpleui.koplugin.zip",
        category="Interface",
        summary="A home screen, navigation bar and reading widgets.",
        description="Build a reading home screen with library shortcuts, book covers and configurable widgets.",
        instructions="Restart KOReader and follow SimpleUI’s welcome screen. Its layout editor and updater are inside SimpleUI settings. With Bookshelf installed, choose one default home screen in the two plugins’ settings.",
    ),
    CatalogueEntry(
        id="zenos",
        name="ZenOS",
        plugin_id="zenos.koplugin",
        repository="xZenLabs/zen-os",
        version="4.0.1",
        tag="v4.0.1",
        asset="zenos.koplugin.zip",
        category="Interface",
        minimum="2026.03",
        summary="A complete reading interface with home and device controls.",
        description="Customise the home screen, library, navigation and reader through Zen Settings. ZenOS replaces several parts of KOReader’s interface.",
        instructions="Restart KOReader and follow the setup guide. Use one lighting scheduler; ZenOS can disable Auto warmth when its own lighting schedules are enabled. Existing Zen UI installations must migrate through their own updater; do not install a second folder.",
    ),
    CatalogueEntry(
        id="bookshelf",
        name="Bookshelf",
        plugin_id="bookshelf.koplugin",
        repository="AndyHazz/bookshelf.koplugin",
        version="5.3.1",
        tag="v5.3.1",
        asset="bookshelf.koplugin.zip",
        category="Library",
        minimum="2025.08",
        summary="Browse your library as shelves of book covers.",
        description="Organise books into shelves with covers, metadata and library shortcuts. Uses KOReader’s built-in Cover browser.",
        instructions="Keep Cover browser enabled. Restart KOReader, then choose Start with → Bookshelf. Works best with KOReader 2026.03 or newer.",
    ),
    CatalogueEntry(
        id="bookends",
        name="Bookends",
        plugin_id="bookends.koplugin",
        repository="AndyHazz/bookends.koplugin",
        version="5.29.1",
        tag="v5.29.1",
        asset="bookends.koplugin-v5.29.1.zip",
        category="Reading",
        summary="Reading headers, footers and progress displays.",
        description="Choose the information shown around your book and save your own reading layouts.",
        instructions="Restart KOReader and open Bookends settings. Use its option to hide the stock status bar if both displays overlap. Keep one header/footer customisation active.",
    ),
    CatalogueEntry(
        id="readinginsights",
        name="Reading Insights",
        plugin_id="readinginsights.koplugin",
        repository="peterboda236/readinginsights.koplugin",
        version="6.14.6",
        tag="v6.14.6",
        asset="readinginsights.koplugin.zip",
        category="Reading",
        summary="Reading history, goals and statistics dashboards.",
        description="Explore reading history and progress using the statistics KOReader already collects. No account is required.",
        instructions="Keep KOReader’s Statistics plugin enabled. Restart and open Tools → Reading insights. If using another sleep screen, leave Reading Insights’ sleep-screen mode off.",
    ),
    CatalogueEntry(
        id="localsend",
        name="LocalSend",
        plugin_id="localsend.koplugin",
        repository="kaikozlov/localsend.koplugin",
        version="1.4.5",
        tag="v1.4.5",
        asset="localsend-koplugin-{variant}.zip",
        category="Transfer",
        summary="Send books between your reader, phone and computer.",
        description="Transfer files over your local network using LocalSend. This plugin includes a native executable selected for the device’s architecture.",
        instructions="Restart KOReader and open Network → LocalSend. Choose a save folder, then start receiving. Use LocalSend on the sending device; keep HTTPS enabled.",
    ),
    CatalogueEntry(
        id="customisablesleepscreen",
        name="Customisable Sleep Screen",
        plugin_id="customisablesleepscreen.koplugin",
        repository="pxlflux/customisablesleepscreen.koplugin",
        version="2.4.0",
        tag="v2.4.0",
        asset="customisablesleepscreen_v2.4.0.zip",
        category="Sleep screen",
        minimum="2026.03",
        summary="Book covers, progress and statistics while asleep.",
        description="Create a sleep screen from book information, reading statistics and saved layouts. Downloaded assets remain under their upstream licences.",
        instructions="Restart KOReader, then enable Settings → Screen → Customisable Sleep Screen. Keep other custom sleep-screen providers off. Preserve your own fonts, icons and presets when migrating the older patch.",
    ),
)

ENTRIES = {entry.id: entry for entry in CATALOGUE}
