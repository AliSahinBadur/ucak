from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AppBrand:
    key: str
    display_name: str
    initials: str
    api_title: str
    data_dir_env: str
    default_data_dir: str
    default_cookie_name: str
    background: str
    panel: str
    line: str
    text: str
    muted: str
    accent: str
    accent_strong: str
    soft: str
    soft_2: str
    halo_1: str
    halo_2: str
    surface_top: str
    card_shadow: str
    card_radius: str


BRANDS = {
    "big_agent": AppBrand(
        key="big_agent",
        display_name="SmartCAE AI",
        initials="SA",
        api_title="SmartCAE AI",
        data_dir_env="BIG_AGENT_DATA_DIR",
        default_data_dir="data",
        default_cookie_name="big_agent_session",
        background="#fbf3f4",
        panel="#ffffff",
        line="#ae848d",
        text="#2a1014",
        muted="#7a555b",
        accent="#c62839",
        accent_strong="#8f1421",
        soft="#fdecef",
        soft_2="#fff9fa",
        halo_1="#ffd9df",
        halo_2="#fff0f2",
        surface_top="#fff7f8",
        card_shadow="rgba(120, 24, 38, 0.08)",
        card_radius="20px",
    ),
    "raporhub": AppBrand(
        key="raporhub",
        display_name="RaporHub",
        initials="RH",
        api_title="RaporHub",
        data_dir_env="RAPORHUB_DATA_DIR",
        default_data_dir="data_raporhub",
        default_cookie_name="raporhub_session",
        background="#f3f6f5",
        panel="#ffffff",
        line="#9fb4b1",
        text="#172321",
        muted="#5c6e6b",
        accent="#087f73",
        accent_strong="#075e56",
        soft="#e4f2f0",
        soft_2="#f8faf9",
        halo_1="#d6eeeb",
        halo_2="#e8edf3",
        surface_top="#fbfcfc",
        card_shadow="rgba(27, 60, 57, 0.10)",
        card_radius="8px",
    ),
}


def normalize_app_variant(value: str | None) -> str:
    normalized = (value or "big_agent").strip().casefold().replace("-", "_")
    if normalized not in BRANDS:
        supported = ", ".join(sorted(BRANDS))
        raise ValueError(f"Unsupported APP_VARIANT '{value}'. Expected one of: {supported}.")
    return normalized


def get_app_brand(value: str | None) -> AppBrand:
    return BRANDS[normalize_app_variant(value)]
