from __future__ import annotations

import sys

from ashare_quant.config import get_settings
from ashare_quant.providers.factory import build_provider_bundle
from ashare_quant.services.market_service import MarketService


def main() -> None:
    strategy = sys.argv[1] if len(sys.argv) > 1 else "trend"
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
    rankings = service.rank_universe(limit=10, strategy=strategy)

    print("A 股量化评分演示 Top 10")
    print("strategy={strategy}".format(strategy=strategy))
    print("-" * 60)
    if rankings.universe_meta is not None:
        print(
            "universe_source={source} cache={cache} stale={stale}".format(
                source=rankings.universe_meta.source_provider,
                cache=rankings.universe_meta.from_cache,
                stale=rankings.universe_meta.used_stale_cache,
            )
        )
        print("-" * 60)
    for index, item in enumerate(rankings.items, start=1):
        print(
            f"{index:>2}. {item.quote.symbol} {item.quote.name:<8} "
            f"score={item.factors.total_score:>6.2f} "
            f"eligible={str(item.factors.eligible):<5} "
            f"pct={item.quote.pct_change:>5.2f}% "
            f"sector={item.quote.sector or '-'} "
            f"notes={'; '.join(item.factors.explanations) or '无'}"
        )


if __name__ == "__main__":
    main()
