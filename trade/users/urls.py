from django.urls import path
from .views import *
urlpatterns = [
    path('register/', register),
    path('login/', login),
    path('logout/', logout),
    path('market-data/', market_data),
    path('start-bot/', start_bot),
    path('stop-bot/', stop_bot),
    path('state/', dashboard_state),
    path('buy/', manual_buy),
    path('sell/', manual_sell),
    path("analytics/", analytics_summary),
    path("history/", trade_history),
    path("export/", export_history_csv),
    path("wallet/reset/", reset_wallet),
    path("wallet/change-asset/", change_asset),
    path("bot/risk/", set_risk_level),
    path("bot/thresholds/", update_thresholds),
    path("bot/candles/", update_candle_limit),
]
