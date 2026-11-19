"""Router package.

Avoid eagerly importing every router during package initialization. This keeps
submodule imports lightweight and prevents unrelated modules from triggering
expensive or optional dependency imports when a single router is needed.
"""

__all__ = [
    "market",
    "stocks",
    "valuation",
    "screener",
    "watchlist",
    "alerts",
    "portfolio",
    "sectors",
    "backtest",
    "admin",
    "ws",
    "fo",
    "ml",
    "ai",
    "auth",
]
