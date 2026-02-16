"""
PolyQuant Strategy - QuantConnect Implementation

Sentiment-driven options trading using Brain Sentiment + IV mean reversion.
Since Polymarket data isn't available, we use Brain Sentiment Indicator as proxy.

Strategy:
- Monitor MAG7 stocks (AAPL, MSFT, NVDA, AMZN, TSLA, META, GOOGL)
- Buy options when sentiment diverges from IV (sentiment high, IV elevated)
- Exit at +50% profit, -30% stop loss, or 1 DTE

Target: Sharpe > 1.0, Max DD < 15%, Win Rate > 55%
"""

from AlgorithmImports import *
from datetime import timedelta


class PolyQuantSentimentStrategy(QCAlgorithm):

    def Initialize(self):
        """Initialize algorithm parameters and data subscriptions"""

        # Backtest period: 1 year
        self.SetStartDate(2023, 1, 1)
        self.SetEndDate(2024, 1, 1)

        # Starting capital
        self.SetCash(10000)

        # MAG7 universe
        self.mag7_tickers = ['AAPL', 'MSFT', 'NVDA', 'AMZN', 'TSLA', 'META', 'GOOGL']
        self.equity_symbols = {}

        for ticker in self.mag7_tickers:
            equity = self.AddEquity(ticker, Resolution.Minute)
            equity.SetDataNormalizationMode(DataNormalizationMode.Raw)
            self.equity_symbols[ticker] = equity.Symbol

            # Add Brain Sentiment data (alternative to Polymarket)
            self.AddData(BrainSentimentIndicator, ticker, Resolution.Daily)

        # Enable options
        self.SetSecurityInitializer(lambda security: security.SetMarketPrice(self.GetLastKnownPrice(security)))

        # Track positions
        self.open_positions = {}  # {option_symbol: PositionData}

        # Risk parameters
        self.max_position_pct = 0.05  # 5% per position
        self.max_sector_exposure = 0.15  # 15% total MAG7
        self.daily_loss_limit = -0.02  # -2% daily stop
        self.max_daily_trades = 10

        self.daily_trades_count = 0
        self.daily_pnl_start = self.Portfolio.TotalPortfolioValue

        # Strategy parameters
        self.min_sentiment_score = 0.70  # High sentiment threshold
        self.min_iv_percentile = 50  # IV must be elevated
        self.max_iv_percentile = 90  # But not extreme fear
        self.target_delta_min = 0.20
        self.target_delta_max = 0.80
        self.max_spread_pct = 0.05  # 5% max bid-ask spread

        # Schedule daily check
        self.Schedule.On(
            self.DateRules.EveryDay(),
            self.TimeRules.AfterMarketOpen('AAPL', 30),
            self.ScanForSignals
        )

        # Monitor positions every hour
        self.Schedule.On(
            self.DateRules.EveryDay(),
            self.TimeRules.Every(timedelta(hours=1)),
            self.MonitorPositions
        )

        # Reset daily counters
        self.Schedule.On(
            self.DateRules.EveryDay(),
            self.TimeRules.AfterMarketOpen('AAPL', 1),
            self.ResetDailyCounters
        )

        self.Debug(f"PolyQuant initialized with ${self.Portfolio.Cash} capital")

    def ResetDailyCounters(self):
        """Reset daily trade limits and P&L tracking"""
        self.daily_trades_count = 0
        self.daily_pnl_start = self.Portfolio.TotalPortfolioValue

    def ScanForSignals(self):
        """
        Scan MAG7 stocks for entry signals

        Entry criteria:
        - High sentiment (proxy for Polymarket bullish probability)
        - Elevated IV (50-90th percentile)
        - Sentiment > IV divergence (mispricing opportunity)
        - Delta 0.20-0.80
        - Spread < 5%
        """

        # Check daily loss limit
        daily_pnl_pct = (self.Portfolio.TotalPortfolioValue - self.daily_pnl_start) / self.daily_pnl_start
        if daily_pnl_pct <= self.daily_loss_limit:
            self.Debug(f"Daily loss limit reached: {daily_pnl_pct:.2%}")
            return

        # Check trade limit
        if self.daily_trades_count >= self.max_daily_trades:
            return

        for ticker in self.mag7_tickers:
            if ticker not in self.equity_symbols:
                continue

            equity_symbol = self.equity_symbols[ticker]

            # Get sentiment data (proxy for Polymarket)
            sentiment = self.GetSentimentScore(ticker)
            if sentiment is None or sentiment < self.min_sentiment_score:
                continue

            # Get option chain
            option_chain = self.OptionChainProvider.GetOptionContractList(equity_symbol, self.Time)
            if not option_chain:
                continue

            # Filter: 7-60 DTE, calls only (long sentiment)
            filtered_contracts = [
                contract for contract in option_chain
                if 7 <= (contract.ID.Date - self.Time).days <= 60
                and contract.ID.OptionRight == OptionRight.Call
            ]

            if not filtered_contracts:
                continue

            # Add option data
            for contract in filtered_contracts[:50]:  # Limit to 50 contracts per ticker
                self.AddOptionContract(contract, Resolution.Minute)

            # Evaluate each contract
            underlying_price = self.Securities[equity_symbol].Price

            for contract in filtered_contracts:
                signal = self.EvaluateContract(contract, underlying_price, sentiment)

                if signal and signal['strength'] > 0.80:
                    self.EnterPosition(contract, signal)
                    break  # One position per ticker at a time

    def GetSentimentScore(self, ticker):
        """
        Get Brain Sentiment score (proxy for Polymarket probability)

        Returns:
            Sentiment score 0-1, or None if unavailable
        """
        try:
            sentiment_data = self.Securities[ticker].Get(BrainSentimentIndicator)
            if sentiment_data:
                # Brain Sentiment ranges -1 to 1, normalize to 0-1
                return (sentiment_data.Sentiment + 1) / 2
        except:
            pass

        return None

    def EvaluateContract(self, contract, underlying_price, sentiment):
        """
        Evaluate option contract for entry signal

        Args:
            contract: OptionContract
            underlying_price: Current underlying price
            sentiment: Sentiment score 0-1

        Returns:
            Signal dict or None
        """
        if contract not in self.Securities:
            return None

        option = self.Securities[contract]

        # Check liquidity
        if option.BidPrice == 0 or option.AskPrice == 0:
            return None

        spread_pct = (option.AskPrice - option.BidPrice) / ((option.AskPrice + option.BidPrice) / 2)
        if spread_pct > self.max_spread_pct:
            return None

        # Get greeks
        iv = option.ImpliedVolatility
        delta = option.Greeks.Delta

        if iv == 0 or delta == 0:
            return None

        # Check delta range
        if not (self.target_delta_min <= delta <= self.target_delta_max):
            return None

        # Calculate IV percentile (approximate: use 30-day lookback)
        iv_percentile = self.EstimateIVPercentile(contract, iv)

        if not (self.min_iv_percentile <= iv_percentile <= self.max_iv_percentile):
            return None

        # Key divergence: sentiment > IV (normalized)
        # High sentiment + elevated IV = market pricing uncertainty, but sentiment shows confidence
        normalized_iv = iv_percentile / 100.0
        divergence = sentiment - normalized_iv

        if divergence < 0.10:  # Need at least 10% divergence
            return None

        # Calculate signal strength
        strength = min(sentiment * 0.5 + divergence * 0.5, 1.0)

        return {
            'strength': strength,
            'entry_price': option.AskPrice,  # Pay the ask for entry
            'delta': delta,
            'iv': iv,
            'iv_percentile': iv_percentile,
            'sentiment': sentiment,
            'divergence': divergence,
            'spread_pct': spread_pct
        }

    def EstimateIVPercentile(self, contract, current_iv):
        """
        Estimate IV percentile (simplified - use 30-day rolling window)

        In production, would use historical IV data
        """
        # TODO: Calculate actual percentile from historical IV
        # For MVP: assume 50-70 is "elevated"

        if current_iv > 0.50:
            return 75  # High IV
        elif current_iv > 0.35:
            return 60  # Elevated
        else:
            return 40  # Normal

    def EnterPosition(self, contract, signal):
        """
        Enter long call position

        Args:
            contract: OptionContract
            signal: Signal dict with strength, entry_price, etc.
        """
        # Risk checks
        current_exposure = sum(
            self.Portfolio[pos].HoldingsValue
            for pos in self.open_positions.keys()
            if self.Portfolio[pos].Invested
        )

        if current_exposure / self.Portfolio.TotalPortfolioValue > self.max_sector_exposure:
            self.Debug("Sector exposure limit reached")
            return

        # Position sizing: fixed % of portfolio
        position_value = self.Portfolio.TotalPortfolioValue * self.max_position_pct
        entry_price = signal['entry_price']
        quantity = int(position_value / (entry_price * 100))

        if quantity < 1:
            return

        # Place order
        self.MarketOrder(contract, quantity)

        # Track position
        self.open_positions[contract] = {
            'entry_time': self.Time,
            'entry_price': entry_price,
            'quantity': quantity,
            'signal_strength': signal['strength'],
            'delta': signal['delta'],
            'iv': signal['iv'],
            'exit_reason': None
        }

        self.daily_trades_count += 1

        self.Debug(f"BUY {contract.ID.Symbol} x{quantity} @ ${entry_price:.2f} | "
                   f"Strength={signal['strength']:.2f} | Divergence={signal['divergence']:.2f}")

    def MonitorPositions(self):
        """
        Check exit triggers for open positions

        Exit triggers:
        1. +50% profit (take profit)
        2. -30% loss (stop loss)
        3. 1 DTE (theta acceleration)
        4. Spread > 8% (liquidity crisis)
        """
        positions_to_close = []

        for contract, pos_data in self.open_positions.items():
            if not self.Portfolio[contract].Invested:
                continue

            if contract not in self.Securities:
                continue

            option = self.Securities[contract]

            # Check liquidity
            if option.BidPrice == 0:
                continue

            # Calculate P&L
            current_price = option.BidPrice
            entry_price = pos_data['entry_price']
            pnl_pct = (current_price - entry_price) / entry_price

            exit_reason = None

            # 1. Take profit: +50%
            if pnl_pct >= 0.50:
                exit_reason = "PROFIT_TARGET"

            # 2. Stop loss: -30%
            elif pnl_pct <= -0.30:
                exit_reason = "STOP_LOSS"

            # 3. Days to expiry <= 1
            elif (contract.ID.Date - self.Time).days <= 1:
                exit_reason = "THETA_BURN"

            # 4. Liquidity crisis: spread > 8%
            elif option.AskPrice > 0:
                spread_pct = (option.AskPrice - option.BidPrice) / ((option.AskPrice + option.BidPrice) / 2)
                if spread_pct > 0.08:
                    exit_reason = "LIQUIDITY"

            if exit_reason:
                positions_to_close.append((contract, exit_reason, current_price, pnl_pct))

        # Close positions
        for contract, reason, exit_price, pnl_pct in positions_to_close:
            self.ExitPosition(contract, reason, exit_price, pnl_pct)

    def ExitPosition(self, contract, reason, exit_price, pnl_pct):
        """
        Exit position

        Args:
            contract: OptionContract
            reason: Exit reason
            exit_price: Exit price
            pnl_pct: P&L percentage
        """
        self.Liquidate(contract)

        pos_data = self.open_positions[contract]
        pos_data['exit_reason'] = reason
        pos_data['exit_price'] = exit_price
        pos_data['pnl_pct'] = pnl_pct

        self.Debug(f"SELL {contract.ID.Symbol} @ ${exit_price:.2f} | "
                   f"P&L={pnl_pct:.1%} | Reason={reason}")

    def OnEndOfAlgorithm(self):
        """Final statistics"""
        self.Debug(f"\n{'='*60}")
        self.Debug(f"BACKTEST COMPLETE")
        self.Debug(f"{'='*60}")
        self.Debug(f"Final Portfolio Value: ${self.Portfolio.TotalPortfolioValue:,.2f}")
        self.Debug(f"Total Return: {(self.Portfolio.TotalPortfolioValue / 10000 - 1):.1%}")
        self.Debug(f"Total Trades: {len(self.open_positions)}")

        # Calculate win rate
        closed_positions = [
            pos for pos in self.open_positions.values()
            if 'pnl_pct' in pos
        ]

        if closed_positions:
            winners = sum(1 for pos in closed_positions if pos['pnl_pct'] > 0)
            win_rate = winners / len(closed_positions)
            avg_win = sum(pos['pnl_pct'] for pos in closed_positions if pos['pnl_pct'] > 0) / max(winners, 1)
            losers = len(closed_positions) - winners
            avg_loss = sum(pos['pnl_pct'] for pos in closed_positions if pos['pnl_pct'] < 0) / max(losers, 1)

            self.Debug(f"Win Rate: {win_rate:.1%}")
            self.Debug(f"Avg Win: {avg_win:.1%}")
            self.Debug(f"Avg Loss: {avg_loss:.1%}")
            self.Debug(f"Profit Factor: {abs(avg_win * winners / (avg_loss * losers)):.2f}")

        self.Debug(f"{'='*60}\n")
