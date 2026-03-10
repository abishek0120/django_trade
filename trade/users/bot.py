import time
import random
from turtle import delay
from .calc import calculate_rsi
from .models import Wallet, BotState, Transaction
from .log import logger
from .shit import get_current_price, get_recent_prices

RUNNING_BOTS = {}


def bot_loop(user_id, delay):
    logger.info(f"BOT LOOP STARTED | user={user_id}")

    BUY_THRESHOLD = 45   # demo friendly
    SELL_THRESHOLD = 55

    while RUNNING_BOTS.get(user_id):
        try:
            wallet, _ = Wallet.objects.get_or_create(user_id=user_id)

            bot_state = BotState.objects.get(user_id=user_id)

            prices = get_recent_prices(
                wallet.asset_symbol,
                bot_state.candle_limit
            )

            rsi = calculate_rsi(prices)
            price = get_current_price(wallet.asset_symbol)

            logger.info(
                f"user={user_id} RSI={rsi} "
                f"BUY_T={BUY_THRESHOLD} SELL_T={SELL_THRESHOLD}"
            )

            # HOLD
            if rsi is None or (BUY_THRESHOLD <= rsi <= SELL_THRESHOLD):
                logger.info(f"user={user_id} DECISION=HOLD")
                time.sleep(delay)
                continue

            # BUY
            if rsi < BUY_THRESHOLD and wallet.balance > price:
                qty = 0.001
                cost = qty * price

                wallet.balance -= cost
                wallet.asset_quantity += qty
                wallet.save()

                Transaction.objects.create(
                    user_id=user_id,
                    action="BUY",
                    price=price,
                    quantity=qty,
                    balance_before=wallet.balance + cost,
                    balance_after=wallet.balance,
                    reason=f"RSI BUY ({rsi})"
                )

                logger.info(
                    f"user={user_id} BUY qty={qty} price={price}"
                )

            # SELL
            elif rsi > SELL_THRESHOLD and wallet.asset_quantity > 0:
                qty = min(0.001, wallet.asset_quantity)
                value = qty * price

                wallet.asset_quantity -= qty
                wallet.balance += value
                wallet.save()

                profit = value  # demo P/L

                Transaction.objects.create(
                    user_id=user_id,
                    action="SELL",
                    price=price,
                    quantity=qty,
                    balance_before=wallet.balance - value,
                    balance_after=wallet.balance,
                    reason=f"RSI SELL ({rsi})"
                )

                logger.info(
                    f"user={user_id} SELL qty={qty} price={price} "
                    f"PROFIT={profit}"
                )

            time.sleep(delay)

        except Exception:
            # ❌ no log spam, silent retry
            time.sleep(delay)

    logger.info(f"BOT LOOP STOPPED | user={user_id}")


def bot_single_step(user_id):
    if not isinstance(user_id, int):
        return

    BUY_THRESHOLD = 45

    try:
        wallet, _ = Wallet.objects.get_or_create(user_id=user_id)

        bot_state = BotState.objects.get(user_id=user_id)

        prices = get_recent_prices(
            wallet.asset_symbol,
            bot_state.candle_limit
        )

        rsi = calculate_rsi(prices)
        price = get_current_price(wallet.asset_symbol)

        logger.info(
            f"INSTANT STEP | user={user_id} RSI={rsi} BUY_T={BUY_THRESHOLD}"
        )

        if rsi and rsi < BUY_THRESHOLD and wallet.balance > price:
            qty = 0.001
            cost = qty * price

            wallet.balance -= cost
            wallet.asset_quantity += qty
            wallet.save()

            Transaction.objects.create(
                user_id=user_id,
                action="BUY",
                price=price,
                quantity=qty,
                balance_before=wallet.balance + cost,
                balance_after=wallet.balance,
                reason=f"Instant RSI BUY ({rsi})"
            )

            logger.info(
                f"INSTANT BUY | user={user_id} qty={qty} price={price}"
            )


    except Exception as e:
        logger.error(f"BOT ERROR | user={user_id} | {e}")
        time.sleep(delay)
