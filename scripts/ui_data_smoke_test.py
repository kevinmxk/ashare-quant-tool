from __future__ import annotations

from ashare_quant.config import get_settings
from ashare_quant.providers.factory import build_provider_bundle
from ashare_quant.services.market_service import MarketService
from ashare_quant.ui.dashboard_data import (
    build_rankings_table,
    build_watchlist_rows,
    parse_watchlist,
    provider_status,
    summarize_rankings,
)


def main() -> None:
    settings = get_settings()
    bundle = build_provider_bundle(settings)
    provider = bundle.default_provider
    service = MarketService(
        provider,
        universe_provider=bundle.universe_provider,
        ranking_provider=bundle.ranking_provider,
        diagnosis_provider=bundle.diagnosis_provider,
        watchlist_provider=bundle.watchlist_provider,
    )

    rankings = service.rank_universe(limit=5, strategy="trend")
    rows = build_rankings_table(rankings)
    watchlist_rows = build_watchlist_rows(service, parse_watchlist("600519,300750,000858"), "value")
    status = provider_status(provider, settings)
    summary = summarize_rankings(rankings)

    print("rankings_rows={value}".format(value=len(rows)))
    print("watchlist_rows={value}".format(value=len(watchlist_rows)))
    print("eligible_count={value}".format(value=summary["eligible_count"]))
    print("provider={value}".format(value=status["active_provider"]))


if __name__ == "__main__":
    main()
