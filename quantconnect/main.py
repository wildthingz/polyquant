"""
PolyQuant VRP Premium Selling Strategy — QuantConnect Backtest

Sells iron condors and credit spreads on Mag 7 stocks, using Brain Sentiment
(Polymarket proxy) as a timing signal. Entry when IV is elevated but sentiment
shows high certainty — the divergence between market-priced uncertainty and
crowd confidence is our edge.

Targets: Sharpe > 0.8, Max DD < 20%, Win Rate > 65%, Return 12-18% annualized
"""

from AlgorithmImports import *
from datetime import timedelta


class PolyQuantVRPStrategy(QCAlgorithm):

    def initialize(self):
        # --- Backtest period: 3 years (bear 2022, bull 2023, mixed 2024) ---
        self.set_start_date(2022, 1, 1)
        self.set_end_date(2024, 12, 31)
        self.set_cash(100_000)
        self.set_warmup(30, Resolution.DAILY)

        # --- MAG7 universe ---
        self.mag7_tickers = ["AAPL", "MSFT", "NVDA", "AMZN", "TSLA", "META", "GOOGL"]
        self.equity_symbols = {}
        self.iv_windows = {}       # {ticker: RollingWindow[float]} — 252 trading days
        self.sentiment_data = {}   # {ticker: BrainSentimentIndicator7Day symbol}

        for ticker in self.mag7_tickers:
            equity = self.add_equity(ticker, Resolution.MINUTE)
            equity.set_data_normalization_mode(DataNormalizationMode.RAW)
            self.equity_symbols[ticker] = equity.symbol

            # Options chain with Crank-Nicolson for accurate Greeks
            option = self.add_option(ticker, Resolution.MINUTE)
            option.set_filter(lambda u: u.strikes(-15, 15).expiration(
                timedelta(days=7), timedelta(days=45)
            ))
            option.price_model = OptionPriceModels.crank_nicolson_fd()

            # Brain Sentiment 7-day (Polymarket proxy)
            self.sentiment_data[ticker] = self.add_data(
                BrainSentimentIndicator7Day, equity.symbol
            ).symbol

            # IV rolling window: 252 trading days
            self.iv_windows[ticker] = RollingWindow[float](252)

        # --- Active spreads tracking ---
        # Each entry: {
        #   'ticker', 'type' (bull_put|bear_call|iron_condor),
        #   'legs' (list of option symbols), 'strategy' (OptionStrategy),
        #   'credit', 'max_loss', 'entry_time', 'expiry', 'quantity'
        # }
        self.active_spreads = []

        # --- Risk parameters ---
        self.max_position_pct = 0.05     # 5% of portfolio per trade (based on max loss)
        self.max_spreads_per_ticker = 3
        self.max_sector_exposure = 0.15  # 15% total
        self.daily_loss_limit = -0.02    # -2% daily halt

        # --- Strategy parameters ---
        self.min_iv_percentile = 50
        self.min_certainty = 0.70
        self.min_divergence = 0.10
        self.target_short_delta = 0.20
        self.target_long_delta = 0.08
        self.min_credit_width_ratio = 0.30
        self.max_bid_ask_spread = 0.05   # 5% on entry
        self.max_bid_ask_exit = 0.08     # 8% liquidity crisis

        # --- Daily state ---
        self.daily_pnl_start = 0
        self.daily_halted = False

        # --- Schedules ---
        self.schedule.on(
            self.date_rules.every_day(),
            self.time_rules.after_market_open("AAPL", 1),
            self.reset_daily,
        )
        self.schedule.on(
            self.date_rules.every_day(),
            self.time_rules.after_market_open("AAPL", 30),
            self.scan_for_entries,
        )
        self.schedule.on(
            self.date_rules.every_day(),
            self.time_rules.every(timedelta(hours=1)),
            self.monitor_positions,
        )

        # --- Stats ---
        self.closed_spreads = []

        self.debug(f"PolyQuant VRP initialized | ${self.portfolio.cash:,.0f} capital | "
                   f"{len(self.mag7_tickers)} tickers")

    # =========================================================================
    # Daily reset
    # =========================================================================

    def reset_daily(self):
        self.daily_pnl_start = self.portfolio.total_portfolio_value
        self.daily_halted = False

    # =========================================================================
    # Entry scanning
    # =========================================================================

    def scan_for_entries(self):
        if self.is_warming_up:
            return

        # Daily loss halt
        if self.daily_halted:
            return
        daily_pnl_pct = ((self.portfolio.total_portfolio_value - self.daily_pnl_start)
                         / self.daily_pnl_start) if self.daily_pnl_start > 0 else 0
        if daily_pnl_pct <= self.daily_loss_limit:
            self.daily_halted = True
            self.debug(f"DAILY HALT | P&L {daily_pnl_pct:.2%}")
            return

        for ticker in self.mag7_tickers:
            self.evaluate_ticker(ticker)

    def evaluate_ticker(self, ticker):
        equity_symbol = self.equity_symbols[ticker]

        # --- Get option chain ---
        chain = self.current_slice.option_chains.get(equity_symbol)
        if chain is None:
            # Try canonical symbol lookup
            for kvp in self.current_slice.option_chains:
                if kvp.Key.underlying == equity_symbol:
                    chain = kvp.Value
                    break
        if chain is None:
            return

        # --- Update IV window with ATM IV ---
        underlying_price = self.securities[equity_symbol].price
        if underlying_price <= 0:
            return

        atm_iv = self._get_atm_iv(chain, underlying_price)
        if atm_iv is not None and atm_iv > 0:
            self.iv_windows[ticker].add(atm_iv)

        # --- IV percentile check ---
        iv_pctl = self.get_iv_percentile(ticker, atm_iv)
        if iv_pctl is None or iv_pctl < self.min_iv_percentile:
            return

        # --- Sentiment ---
        sentiment = self.get_sentiment(ticker)
        if sentiment is None:
            return

        # --- Certainty & divergence ---
        certainty = max(sentiment, 1 - sentiment)
        if certainty < self.min_certainty:
            return

        divergence = certainty - (1 - iv_pctl / 100)
        if divergence < self.min_divergence:
            return

        # --- Per-ticker position limit ---
        ticker_count = sum(1 for s in self.active_spreads if s["ticker"] == ticker)
        if ticker_count >= self.max_spreads_per_ticker:
            return

        # --- Sector exposure check ---
        total_exposure = sum(s["max_loss"] * s["quantity"] for s in self.active_spreads)
        if total_exposure / self.portfolio.total_portfolio_value >= self.max_sector_exposure:
            return

        # --- Route to trade type based on sentiment ---
        if sentiment > 0.70:
            self.enter_bull_put_spread(ticker, chain, underlying_price, iv_pctl, sentiment)
        elif sentiment < 0.30:
            self.enter_bear_call_spread(ticker, chain, underlying_price, iv_pctl, sentiment)
        elif 0.40 <= sentiment <= 0.60:
            self.enter_iron_condor(ticker, chain, underlying_price, iv_pctl, sentiment)
        # else: 0.30-0.40 or 0.60-0.70 — skip, not confident enough

    # =========================================================================
    # Entry: Bull Put Spread (sentiment > 0.70)
    # =========================================================================

    def enter_bull_put_spread(self, ticker, chain, underlying_price, iv_pctl, sentiment):
        expiry = self.select_expiry(chain)
        if expiry is None:
            return

        puts = [c for c in chain
                if c.right == OptionRight.PUT and c.expiry == expiry]
        if len(puts) < 2:
            return

        # Find short put near 0.20 delta, long put near 0.08 delta
        short_put = self._select_by_delta(puts, self.target_short_delta)
        long_put = self._select_by_delta(
            [p for p in puts if p.strike < short_put.strike], self.target_long_delta
        ) if short_put else None

        if short_put is None or long_put is None:
            return
        if long_put.strike >= short_put.strike:
            return

        # Liquidity check
        if not self.check_liquidity([short_put, long_put]):
            return

        # Credit and width
        credit = short_put.bid_price - long_put.ask_price
        width = (short_put.strike - long_put.strike)
        if width <= 0 or credit <= 0:
            return
        if credit / width < self.min_credit_width_ratio:
            return

        max_loss_per_contract = (width - credit) * 100
        quantity = self._calc_quantity(max_loss_per_contract)
        if quantity < 1:
            return

        # Place order via OptionStrategies
        strategy = OptionStrategies.bull_put_spread(
            equity_symbol=self.equity_symbols[ticker],
            higher_strike=short_put.strike,
            lower_strike=long_put.strike,
            expiration=expiry,
        )
        tickets = self.buy(strategy, quantity)

        self.active_spreads.append({
            "ticker": ticker,
            "type": "bull_put",
            "legs": [short_put.symbol, long_put.symbol],
            "strategy": strategy,
            "credit": credit,
            "max_loss": max_loss_per_contract / 100,
            "entry_time": self.time,
            "expiry": expiry,
            "quantity": quantity,
            "iv_pctl": iv_pctl,
            "sentiment": sentiment,
        })

        self.debug(f"ENTER bull_put | {ticker} | "
                   f"short={short_put.strike} long={long_put.strike} | "
                   f"credit=${credit:.2f} width=${width:.2f} | "
                   f"qty={quantity} | IV%={iv_pctl:.0f} sent={sentiment:.2f}")

    # =========================================================================
    # Entry: Bear Call Spread (sentiment < 0.30)
    # =========================================================================

    def enter_bear_call_spread(self, ticker, chain, underlying_price, iv_pctl, sentiment):
        expiry = self.select_expiry(chain)
        if expiry is None:
            return

        calls = [c for c in chain
                 if c.right == OptionRight.CALL and c.expiry == expiry]
        if len(calls) < 2:
            return

        # Find short call near 0.20 delta, long call near 0.08 delta
        short_call = self._select_by_delta(calls, self.target_short_delta)
        long_call = self._select_by_delta(
            [c for c in calls if c.strike > short_call.strike], self.target_long_delta
        ) if short_call else None

        if short_call is None or long_call is None:
            return
        if long_call.strike <= short_call.strike:
            return

        if not self.check_liquidity([short_call, long_call]):
            return

        credit = short_call.bid_price - long_call.ask_price
        width = (long_call.strike - short_call.strike)
        if width <= 0 or credit <= 0:
            return
        if credit / width < self.min_credit_width_ratio:
            return

        max_loss_per_contract = (width - credit) * 100
        quantity = self._calc_quantity(max_loss_per_contract)
        if quantity < 1:
            return

        strategy = OptionStrategies.bear_call_spread(
            equity_symbol=self.equity_symbols[ticker],
            lower_strike=short_call.strike,
            higher_strike=long_call.strike,
            expiration=expiry,
        )
        tickets = self.buy(strategy, quantity)

        self.active_spreads.append({
            "ticker": ticker,
            "type": "bear_call",
            "legs": [short_call.symbol, long_call.symbol],
            "strategy": strategy,
            "credit": credit,
            "max_loss": max_loss_per_contract / 100,
            "entry_time": self.time,
            "expiry": expiry,
            "quantity": quantity,
            "iv_pctl": iv_pctl,
            "sentiment": sentiment,
        })

        self.debug(f"ENTER bear_call | {ticker} | "
                   f"short={short_call.strike} long={long_call.strike} | "
                   f"credit=${credit:.2f} width=${width:.2f} | "
                   f"qty={quantity} | IV%={iv_pctl:.0f} sent={sentiment:.2f}")

    # =========================================================================
    # Entry: Iron Condor (sentiment 0.40-0.60)
    # =========================================================================

    def enter_iron_condor(self, ticker, chain, underlying_price, iv_pctl, sentiment):
        expiry = self.select_expiry(chain)
        if expiry is None:
            return

        puts = [c for c in chain
                if c.right == OptionRight.PUT and c.expiry == expiry]
        calls = [c for c in chain
                 if c.right == OptionRight.CALL and c.expiry == expiry]
        if len(puts) < 2 or len(calls) < 2:
            return

        # Put side: short ~0.20 delta, long ~0.08 delta
        short_put = self._select_by_delta(puts, self.target_short_delta)
        long_put = self._select_by_delta(
            [p for p in puts if p.strike < short_put.strike], self.target_long_delta
        ) if short_put else None

        # Call side: short ~0.20 delta, long ~0.08 delta
        short_call = self._select_by_delta(calls, self.target_short_delta)
        long_call = self._select_by_delta(
            [c for c in calls if c.strike > short_call.strike], self.target_long_delta
        ) if short_call else None

        if any(x is None for x in [short_put, long_put, short_call, long_call]):
            return
        if long_put.strike >= short_put.strike or long_call.strike <= short_call.strike:
            return

        all_legs = [short_put, long_put, short_call, long_call]
        if not self.check_liquidity(all_legs):
            return

        put_credit = short_put.bid_price - long_put.ask_price
        call_credit = short_call.bid_price - long_call.ask_price
        total_credit = put_credit + call_credit

        put_width = short_put.strike - long_put.strike
        call_width = long_call.strike - short_call.strike
        max_width = max(put_width, call_width)

        if max_width <= 0 or total_credit <= 0:
            return

        # Credit/width ratio uses wider side (worst case)
        if total_credit / max_width < self.min_credit_width_ratio:
            return

        max_loss_per_contract = (max_width - total_credit) * 100
        quantity = self._calc_quantity(max_loss_per_contract)
        if quantity < 1:
            return

        strategy = OptionStrategies.iron_condor(
            equity_symbol=self.equity_symbols[ticker],
            long_put_strike=long_put.strike,
            short_put_strike=short_put.strike,
            short_call_strike=short_call.strike,
            long_call_strike=long_call.strike,
            expiration=expiry,
        )
        tickets = self.buy(strategy, quantity)

        self.active_spreads.append({
            "ticker": ticker,
            "type": "iron_condor",
            "legs": [s.symbol for s in all_legs],
            "strategy": strategy,
            "credit": total_credit,
            "max_loss": max_loss_per_contract / 100,
            "entry_time": self.time,
            "expiry": expiry,
            "quantity": quantity,
            "iv_pctl": iv_pctl,
            "sentiment": sentiment,
        })

        self.debug(f"ENTER iron_condor | {ticker} | "
                   f"puts={long_put.strike}/{short_put.strike} "
                   f"calls={short_call.strike}/{long_call.strike} | "
                   f"credit=${total_credit:.2f} | qty={quantity} | "
                   f"IV%={iv_pctl:.0f} sent={sentiment:.2f}")

    # =========================================================================
    # Position monitoring & exits
    # =========================================================================

    def monitor_positions(self):
        if self.is_warming_up or not self.active_spreads:
            return

        to_close = []

        for i, spread in enumerate(self.active_spreads):
            # Unrealized P&L across all legs (short credit = we want value to decrease)
            unrealized = sum(
                self.portfolio[sym].unrealized_profit
                for sym in spread["legs"]
                if sym in self.portfolio
            )

            credit_received = spread["credit"] * spread["quantity"] * 100
            exit_reason = None

            # 1. Take profit: captured >= 50% of credit
            if unrealized >= 0.50 * credit_received:
                exit_reason = "TAKE_PROFIT"

            # 2. Stop loss: loss >= 1x credit (spread value doubled)
            elif unrealized <= -credit_received:
                exit_reason = "STOP_LOSS"

            # 3. Theta burn: DTE <= 1
            elif (spread["expiry"] - self.time).days <= 1:
                exit_reason = "THETA_BURN"

            # 4. Liquidity crisis: any leg spread > 8%
            elif self._any_leg_illiquid(spread["legs"]):
                exit_reason = "LIQUIDITY"

            if exit_reason:
                to_close.append((i, exit_reason, unrealized))

        # Close in reverse order to keep indices valid
        for i, reason, pnl in sorted(to_close, key=lambda x: x[0], reverse=True):
            self.close_spread(i, reason, pnl)

    def close_spread(self, index, reason, unrealized_pnl):
        spread = self.active_spreads[index]

        # Liquidate all legs
        for sym in spread["legs"]:
            if self.portfolio[sym].invested:
                self.liquidate(sym)

        self.debug(f"EXIT {spread['type']} | {spread['ticker']} | "
                   f"reason={reason} | P&L=${unrealized_pnl:,.2f} | "
                   f"held {(self.time - spread['entry_time']).days}d")

        # Record for stats
        self.closed_spreads.append({
            "ticker": spread["ticker"],
            "type": spread["type"],
            "credit": spread["credit"],
            "quantity": spread["quantity"],
            "pnl": unrealized_pnl,
            "reason": reason,
            "held_days": (self.time - spread["entry_time"]).days,
            "iv_pctl": spread["iv_pctl"],
            "sentiment": spread["sentiment"],
        })

        self.active_spreads.pop(index)

    # =========================================================================
    # Helpers
    # =========================================================================

    def select_expiry(self, chain):
        """Find expiry nearest to 30 DTE within the 7-45 day window."""
        target_dte = 30
        expiries = sorted(set(c.expiry for c in chain))
        valid = [e for e in expiries if 7 <= (e - self.time).days <= 45]
        if not valid:
            return None
        return min(valid, key=lambda e: abs((e - self.time).days - target_dte))

    def get_iv_percentile(self, ticker, current_iv):
        """Percentile rank of current ATM IV vs. 252-day window."""
        window = self.iv_windows[ticker]
        if not window.is_ready or current_iv is None:
            return None
        count_below = sum(1 for i in range(window.count) if window[i] < current_iv)
        return (count_below / window.count) * 100

    def get_sentiment(self, ticker):
        """
        Read BrainSentimentIndicator7Day, normalize from [-1, +1] to [0, 1].
        Returns None if unavailable.
        """
        sym = self.sentiment_data.get(ticker)
        if sym is None or sym not in self.securities:
            return None
        security = self.securities[sym]
        if security is None or not security.has_data:
            return None
        try:
            value = security.price  # BrainSentiment stores sentiment as Price
            # Clamp to [-1, 1] then normalize to [0, 1]
            value = max(-1.0, min(1.0, value))
            return (value + 1) / 2
        except Exception:
            return None

    def check_liquidity(self, contracts):
        """Check bid-ask spread < 5% on all legs."""
        for c in contracts:
            if c.bid_price <= 0 or c.ask_price <= 0:
                return False
            mid = (c.bid_price + c.ask_price) / 2
            if mid <= 0:
                return False
            spread_pct = (c.ask_price - c.bid_price) / mid
            if spread_pct > self.max_bid_ask_spread:
                return False
        return True

    def _get_atm_iv(self, chain, underlying_price):
        """Get ATM implied volatility from the chain."""
        atm = min(chain, key=lambda c: abs(c.strike - underlying_price), default=None)
        if atm is None:
            return None
        return atm.implied_volatility if atm.implied_volatility > 0 else None

    def _select_by_delta(self, contracts, target_delta):
        """Select the contract whose absolute delta is closest to target."""
        valid = [c for c in contracts
                 if c.greeks is not None and c.greeks.delta != 0]
        if not valid:
            return None
        return min(valid, key=lambda c: abs(abs(c.greeks.delta) - target_delta))

    def _calc_quantity(self, max_loss_per_contract):
        """Position size: max 5% of portfolio risk per trade."""
        if max_loss_per_contract <= 0:
            return 0
        risk_budget = self.portfolio.total_portfolio_value * self.max_position_pct
        return int(risk_budget / max_loss_per_contract)

    def _any_leg_illiquid(self, leg_symbols):
        """Check if any leg has bid-ask spread > 8%."""
        for sym in leg_symbols:
            if sym not in self.securities:
                continue
            sec = self.securities[sym]
            if sec.bid_price <= 0 or sec.ask_price <= 0:
                continue
            mid = (sec.bid_price + sec.ask_price) / 2
            if mid <= 0:
                continue
            if (sec.ask_price - sec.bid_price) / mid > self.max_bid_ask_exit:
                return True
        return False

    # =========================================================================
    # End of algorithm stats
    # =========================================================================

    def on_end_of_algorithm(self):
        self.debug(f"\n{'='*60}")
        self.debug("POLYQUANT VRP BACKTEST COMPLETE")
        self.debug(f"{'='*60}")
        self.debug(f"Final Value:  ${self.portfolio.total_portfolio_value:,.2f}")
        self.debug(f"Total Return: {(self.portfolio.total_portfolio_value / 100_000 - 1):.1%}")
        self.debug(f"Total Trades: {len(self.closed_spreads)}")

        if not self.closed_spreads:
            self.debug("No closed trades to analyze.")
            return

        winners = [s for s in self.closed_spreads if s["pnl"] > 0]
        losers = [s for s in self.closed_spreads if s["pnl"] <= 0]
        win_rate = len(winners) / len(self.closed_spreads)

        avg_win = (sum(s["pnl"] for s in winners) / len(winners)) if winners else 0
        avg_loss = (sum(s["pnl"] for s in losers) / len(losers)) if losers else 0
        total_pnl = sum(s["pnl"] for s in self.closed_spreads)

        self.debug(f"Win Rate:     {win_rate:.1%} ({len(winners)}W / {len(losers)}L)")
        self.debug(f"Avg Win:      ${avg_win:,.2f}")
        self.debug(f"Avg Loss:     ${avg_loss:,.2f}")
        if losers and avg_loss != 0:
            self.debug(f"Profit Factor: {abs(sum(s['pnl'] for s in winners) / sum(s['pnl'] for s in losers)):.2f}")
        self.debug(f"Total P&L:    ${total_pnl:,.2f}")

        # Breakdown by trade type
        for trade_type in ["bull_put", "bear_call", "iron_condor"]:
            trades = [s for s in self.closed_spreads if s["type"] == trade_type]
            if trades:
                type_pnl = sum(s["pnl"] for s in trades)
                type_wr = sum(1 for s in trades if s["pnl"] > 0) / len(trades)
                self.debug(f"  {trade_type:14s}: {len(trades):3d} trades | "
                           f"WR {type_wr:.0%} | P&L ${type_pnl:,.2f}")

        # Breakdown by exit reason
        for reason in ["TAKE_PROFIT", "STOP_LOSS", "THETA_BURN", "LIQUIDITY"]:
            trades = [s for s in self.closed_spreads if s["reason"] == reason]
            if trades:
                self.debug(f"  {reason:14s}: {len(trades):3d} exits")

        avg_hold = sum(s["held_days"] for s in self.closed_spreads) / len(self.closed_spreads)
        self.debug(f"Avg Hold:     {avg_hold:.1f} days")
        self.debug(f"{'='*60}\n")
