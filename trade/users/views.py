from django.contrib.auth import authenticate, get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from rest_framework.authtoken.models import Token
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException, BinanceOrderException
from .shit import client,get_recent_prices,get_current_price
import logging
import time
import threading
from .bot import bot_loop, RUNNING_BOTS,bot_single_step
from .models import BotState, Wallet,Transaction,BotLog
from .log import logger
from .calc import *
import csv
from django.http import HttpResponse



User = get_user_model()

def reset_all_bots_on_start():
    try:
        BotState.objects.all().update(is_running=False)
        RUNNING_BOTS.clear()
    except Exception:
            pass  # DB not ready yet
reset_all_bots_on_start()

MAX_LOGS = 100  # last N logs

def log_event(user, level, source, message):
    BotLog.objects.create(
        user=user,
        level=level,
        source=source,
        message=message
    )

    # enforce last N logs
    qs = BotLog.objects.filter(user=user).order_by("-created_at")
    if qs.count() > MAX_LOGS:
        qs[MAX_LOGS:].delete()



@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    name = request.data.get('name', '')
    phone = request.data.get('phone')
    password = request.data.get('password')

    if not phone or not password:
        return Response(
            {"detail": "Phone and password are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    if User.objects.filter(phone=phone).exists():
        return Response(
            {"detail": "User already exists."},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = User.objects.create_user(
        phone=phone,
        password=password,
        name=name
    )

    token, _ = Token.objects.get_or_create(user=user)

    return Response({
        "user_id": user.id,
        "name": user.name,
        "phone": user.phone,
        "token": token.key,
        "message": "Registered successfully."
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    phone = request.data.get('phone')
    password = request.data.get('password')

    if not phone or not password:
        return Response(
            {"detail": "Phone and password are required."},
            status=status.HTTP_400_BAD_REQUEST
        )

    user = authenticate(request, username=phone, password=password)
    if not user:
        return Response(
            {"detail": "Invalid credentials."},
            status=status.HTTP_400_BAD_REQUEST
        )

    token, _ = Token.objects.get_or_create(user=user)

    return Response({"user_id": user.id,"name": user.name,"phone": user.phone,"token": token.key,"message": "Logged in."}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout(request):
    request.auth.delete()
    return Response({"message": "Logged out."},status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def market_data(request):
    try:
        symbol = request.GET.get("symbol", "BTCUSDT")
        limit = int(request.GET.get("limit", 77))

        klines = client.get_klines(
            symbol=symbol,
            interval=Client.KLINE_INTERVAL_1MINUTE,
            limit=limit
        )

        prices = [float(k[4]) for k in klines]
        timestamps = [k[0] for k in klines]

        return Response({
            "symbol": symbol,
            "prices": prices,
            "timestamps": timestamps
        })

    except Exception:
        return Response(
            {"message": "Cannot connect to Binance. Check internet."},
            status=503
        )


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def start_bot(request):
    user = request.user

    bot_state, _ = BotState.objects.get_or_create(user=user)
    Wallet.objects.get_or_create(user=user)

    if bot_state.is_running:
        return Response({"message": "Bot already running"})

    bot_state.is_running = True
    bot_state.trade_delay = 3  
    bot_state.save()

    RUNNING_BOTS[user.id] = True

    logger.info(f"BOT STARTED | user={user.id}")

    from .bot import bot_single_step
    bot_single_step(user.id)

    t = threading.Thread(
        target=bot_loop,
        args=(user.id, bot_state.trade_delay),
        daemon=True
    )
    t.start()

    return Response({"message": "Bot started"})


# views.py
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def stop_bot(request):
    user = request.user

    try:
        bot_state = BotState.objects.get(user=user)
        wallet, _ = Wallet.objects.get_or_create(user=user)  # safer
    except BotState.DoesNotExist:
        return Response({"message": "Bot not found"})

    bot_state.is_running = False
    bot_state.save()

    RUNNING_BOTS[user.id] = False

    logger.info(
        f"BOT STOPPED | user={user.id} "
        f"FINAL_BALANCE={wallet.balance} "
        f"SHARES={wallet.asset_quantity}"
    )

    return Response({"message": "Bot stopped"})



@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def dashboard_state(request):
    user = request.user
    wallet, _ = Wallet.objects.get_or_create(user=user)
    bot_state, _ = BotState.objects.get_or_create(user=user)
    risk_level = bot_state.risk_level

    return Response({
        "bot_running": bot_state.is_running,
        "balance": wallet.balance,
        "asset": wallet.asset_symbol,
        "quantity": wallet.asset_quantity,
        "candle_limit": bot_state.candle_limit,
        "risk_level": risk_level,
        "buy_rsi": bot_state.buy_rsi,
        "sell_rsi": bot_state.sell_rsi,
        "username": user.name
    })

#new thing
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def manual_buy(request):
    user = request.user
    wallet, _ = Wallet.objects.get_or_create(user=user)


    qty = float(request.data.get("quantity", 0))
    if qty <= 0:
        return Response({"message": "Quantity required"}, status=400)

    price = get_current_price(wallet.asset_symbol)
    cost = qty * price

    if wallet.balance < cost:
        return Response({"message": "Insufficient balance"}, status=400)

    balance_before = wallet.balance

    wallet.balance -= cost
    wallet.asset_quantity += qty
    wallet.save()

    Transaction.objects.create(
        user=user,
        action="BUY",
        price=price,
        quantity=qty,
        balance_before=balance_before,
        balance_after=wallet.balance,
        reason="Manual buy"
    )

    logger.info(f"BUY | user={user.name} qty={qty} price={price}")

    return Response({
        "message": "Buy successful",
        "balance": wallet.balance,
        "total_shares": wallet.asset_quantity
    })

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def manual_sell(request):
    user = request.user
    wallet, _ = Wallet.objects.get_or_create(user=user)


    qty = float(request.data.get("quantity", 0))
    if qty <= 0:
        return Response({"message": "Quantity required"}, status=400)

    if wallet.asset_quantity < qty:
        return Response({"message": "Not enough shares"}, status=400)

    price = get_current_price(wallet.asset_symbol)
    value = qty * price

    balance_before = wallet.balance

    wallet.asset_quantity -= qty
    wallet.balance += value
    wallet.save()

    Transaction.objects.create(
        user=user,
        action="SELL",
        price=price,
        quantity=qty,
        balance_before=balance_before,
        balance_after=wallet.balance,
        reason="Manual sell"
    )

    logger.info(f"SELL | user={user.name} qty={qty} price={price}")

    return Response({
        "message": "Sell successful",
        "balance": wallet.balance,
        "total_shares": wallet.asset_quantity
    })

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def analytics_summary(request):
    user = request.user
    response = {}

    # 1) Price vs Time
    try:
        price_data = get_price_data()
        response["price_vs_time"] = {
            "status": "ok",
            "data": price_data,
            "error": None
        }
    except Exception as e:
        price_data = []
        response["price_vs_time"] = {
            "status": "error",
            "data": None,
            "error": str(e)
        }

    # 2) RSI vs Time
    try:
        rsi_data = rsi_vs_time(price_data)
        response["rsi_vs_time"] = {
            "status": "ok",
            "thresholds": {"buy": 45, "sell": 55},
            "data": rsi_data,
            "error": None
        }
    except Exception as e:
        rsi_data = []
        response["rsi_vs_time"] = {
            "status": "error",
            "data": None,
            "error": str(e)
        }

    # 3) Profit vs Loss
    try:
        pnl_data = profit_vs_loss(user)
        response["profit_vs_loss"] = {
            "status": "ok",
            "data": pnl_data,
            "error": None
        }
    except Exception as e:
        response["profit_vs_loss"] = {
            "status": "error",
            "data": None,
            "error": str(e)
        }

    # 4) ROI
    try:
        roi_data = calculate_roi(user)
        response["roi"] = {
            "status": "ok",
            **roi_data,
            "error": None
        }
    except Exception as e:
        response["roi"] = {
            "status": "error",
            "error": str(e)
        }

    # 5) Next Price (Regression Output)
    try:
        response["next_price"] = {
            "status": "ok",
            **next_price(price_data),
            "error": None
        }
    except Exception as e:
        response["next_price"] = {
            "status": "error",
            "error": str(e)
        }

    # 6) Next RSI (Regression Output)
    try:
        response["next_rsi"] = {
            "status": "ok",
            **next_rsi(rsi_data),
            "error": None
        }
    except Exception as e:
        response["next_rsi"] = {
            "status": "error",
            "error": str(e)
        }

    return Response(response, status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def trade_history(request):
    user = request.user
    wallet, _ = Wallet.objects.get_or_create(user=user)
    transactions = Transaction.objects.filter(user=user).order_by("-created_at")

    history = []
    cumulative_pnl = 0.0

    for tx in transactions:
        profit_loss = 0.0
        if tx.action == "SELL":
            profit_loss = tx.balance_after - tx.balance_before
            cumulative_pnl += profit_loss

        history.append({
            "time": tx.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "action": tx.action,
            "price": tx.price,
            "quantity": tx.quantity,
            "balance_before": tx.balance_before,
            "balance_after": tx.balance_after,
            "profit_loss": round(profit_loss, 2),
            "reason": tx.reason,
            "asset_symbol": wallet.asset_symbol,
            "event_type": "BOT" if "RSI" in tx.reason else "MANUAL"
        })

    return Response({
        "status": "ok",
        "count": len(history),
        "history": history
    }, status=status.HTTP_200_OK)


@api_view(['GET',"POST"])
@permission_classes([IsAuthenticated])
def export_history_csv(request):
    user = request.user
    wallet = Wallet.objects.get(user=user)

    transactions = Transaction.objects.filter(user=user).order_by("created_at")

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="trade_history.csv"'

    writer = csv.writer(response)
    writer.writerow([
        "Time", "Action", "Price", "Quantity",
        "Balance Before", "Balance After",
        "Profit/Loss", "Asset", "Reason"
    ])

    for tx in transactions:
        profit_loss = 0.0
        if tx.action == "SELL":
            profit_loss = tx.balance_after - tx.balance_before

        writer.writerow([
            tx.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            tx.action,
            tx.price,
            tx.quantity,
            tx.balance_before,
            tx.balance_after,
            round(profit_loss, 2),
            wallet.asset_symbol,
            tx.reason
        ])

    return response


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reset_wallet(request):
    user = request.user

    wallet,_ = Wallet.objects.get_or_create(user=user)
    bot_state,_ = BotState.objects.get_or_create(user=user)

    wallet.balance = 1000000.0
    wallet.asset_quantity = 0.0
    wallet.save()

    bot_state.is_running = False
    bot_state.save()

    Transaction.objects.filter(user=user).delete()

    return Response({
        "message": "Wallet reset successfully",
        "balance": wallet.balance,
        "asset_quantity": wallet.asset_quantity
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_asset(request):
    user = request.user
    new_asset = request.data.get("asset_symbol")

    if not new_asset:
        return Response(
            {"error": "asset_symbol is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    wallet = Wallet.objects.get(user=user)
    bot_state = BotState.objects.get(user=user)

    wallet.asset_symbol = new_asset
    wallet.asset_quantity = 0.0
    wallet.save()

    bot_state.is_running = False
    bot_state.save()

    return Response({
        "message": "Asset changed successfully",
        "asset_symbol": new_asset
    }, status=status.HTTP_200_OK)


@api_view(["GET",'POST'])
@permission_classes([IsAuthenticated])
def set_risk_level(request):
    user = request.user
    level = request.data.get("risk_level")

    if level not in ["LOW", "MEDIUM", "HIGH"]:
        return Response(
            {"error": "Invalid risk level"},
            status=status.HTTP_400_BAD_REQUEST
        )

    bot_state = BotState.objects.get(user=user)
    bot_state.risk_level = level
    bot_state.save()

    return Response({
        "message": "Risk level updated",
        "risk_level": level
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_thresholds(request):
    user = request.user
    buy = request.data.get("buy_rsi")
    sell = request.data.get("sell_rsi")

    if buy is None or sell is None:
        return Response(
            {"error": "buy_rsi and sell_rsi are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    bot_state = BotState.objects.get(user=user)
    bot_state.buy_rsi = float(buy)
    bot_state.sell_rsi = float(sell)
    bot_state.save()

    return Response({
        "message": "Thresholds updated",
        "buy_rsi": bot_state.buy_rsi,
        "sell_rsi": bot_state.sell_rsi
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_candle_limit(request):
    user = request.user
    limit = request.data.get("candle_limit")

    if not limit or int(limit) < 10:
        return Response(
            {"error": "candle_limit must be >= 10"},
            status=status.HTTP_400_BAD_REQUEST
        )

    bot_state = BotState.objects.get(user=user)
    bot_state.candle_limit = int(limit)
    bot_state.save()

    return Response({
        "message": "Candle count updated",
        "candle_limit": bot_state.candle_limit
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_logs(request):
    user = request.user

    logs = BotLog.objects.filter(user=user).order_by("created_at")

    data = []
    for log in logs:
        data.append({
            "time": log.created_at.strftime("%H:%M:%S"),
            "level": log.level,
            "source": log.source,
            "message": log.message
        })

    return Response({
        "status": "ok",
        "count": len(data),
        "logs": data
    }, status=status.HTTP_200_OK)
