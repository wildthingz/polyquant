# Mathematical Specifications

Complete mathematical formulations for option pricing, Greeks calculation, implied volatility solving, and expected value computation.

## Table of Contents

1. [Black-Scholes Model](#black-scholes-model)
2. [The Greeks](#the-greeks)
3. [Implied Volatility Solver](#implied-volatility-solver)
4. [Expected Value Calculation](#expected-value-calculation)
5. [Position Sizing (Kelly Criterion)](#position-sizing-kelly-criterion)
6. [IV Percentile](#iv-percentile)

---

## Black-Scholes Model

### Call Option Pricing

$$
C = S \cdot N(d_1) - K \cdot e^{-rT} \cdot N(d_2)
$$

Where:
$$
d_1 = \frac{\ln(S/K) + (r + \sigma^2/2)T}{\sigma\sqrt{T}}
$$

$$
d_2 = d_1 - \sigma\sqrt{T}
$$

**Variables**:
- $C$ = Call option price
- $S$ = Current stock price
- $K$ = Strike price
- $r$ = Risk-free interest rate (use 10-year Treasury rate)
- $T$ = Time to expiration (in years)
- $\sigma$ = Implied volatility (annualized)
- $N(\cdot)$ = Cumulative standard normal distribution

### Put Option Pricing

$$
P = K \cdot e^{-rT} \cdot N(-d_2) - S \cdot N(-d_1)
$$

### C++ Implementation

```c++
#include <cmath>
#include <algorithm>

class BlackScholes {
public:
    // Standard normal CDF (Abramowitz & Stegun approximation)
    static double norm_cdf(double x) {
        static const double a1 =  0.254829592;
        static const double a2 = -0.284496736;
        static const double a3 =  1.421413741;
        static const double a4 = -1.453152027;
        static const double a5 =  1.061405429;
        static const double p  =  0.3275911;

        int sign = (x < 0) ? -1 : 1;
        x = std::abs(x) / std::sqrt(2.0);

        double t = 1.0 / (1.0 + p * x);
        double y = 1.0 - (((((a5 * t + a4) * t) + a3) * t + a2) * t + a1) * t * std::exp(-x * x);

        return 0.5 * (1.0 + sign * y);
    }

    // Standard normal PDF
    static double norm_pdf(double x) {
        static const double inv_sqrt_2pi = 0.3989422804014327;
        return inv_sqrt_2pi * std::exp(-0.5 * x * x);
    }

    // Calculate d1
    static double d1(double S, double K, double r, double sigma, double T) {
        return (std::log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * std::sqrt(T));
    }

    // Calculate d2
    static double d2(double S, double K, double r, double sigma, double T) {
        return d1(S, K, r, sigma, T) - sigma * std::sqrt(T);
    }

    // Call option price
    static double call_price(double S, double K, double r, double sigma, double T) {
        if (T <= 0) return std::max(S - K, 0.0);

        double d1_val = d1(S, K, r, sigma, T);
        double d2_val = d2(S, K, r, sigma, T);

        return S * norm_cdf(d1_val) - K * std::exp(-r * T) * norm_cdf(d2_val);
    }

    // Put option price
    static double put_price(double S, double K, double r, double sigma, double T) {
        if (T <= 0) return std::max(K - S, 0.0);

        double d1_val = d1(S, K, r, sigma, T);
        double d2_val = d2(S, K, r, sigma, T);

        return K * std::exp(-r * T) * norm_cdf(-d2_val) - S * norm_cdf(-d1_val);
    }
};
```

---

## The Greeks

### Delta (Δ): Rate of Change w.r.t. Underlying Price

**Call Delta**:
$$
\Delta_{\text{call}} = N(d_1)
$$

**Put Delta**:
$$
\Delta_{\text{put}} = N(d_1) - 1
$$

**Range**:
- Call: $[0, 1]$
- Put: $[-1, 0]$

**C++ Implementation**:
```c++
class Greeks {
public:
    static double call_delta(double S, double K, double r, double sigma, double T) {
        double d1_val = BlackScholes::d1(S, K, r, sigma, T);
        return BlackScholes::norm_cdf(d1_val);
    }

    static double put_delta(double S, double K, double r, double sigma, double T) {
        return call_delta(S, K, r, sigma, T) - 1.0;
    }
};
```

### Gamma (Γ): Rate of Change of Delta

$$
\Gamma = \frac{N'(d_1)}{S \sigma \sqrt{T}}
$$

Where $N'(x)$ is the standard normal PDF.

**Same for calls and puts**.

**C++ Implementation**:
```c++
static double gamma(double S, double K, double r, double sigma, double T) {
    double d1_val = BlackScholes::d1(S, K, r, sigma, T);
    return BlackScholes::norm_pdf(d1_val) / (S * sigma * std::sqrt(T));
}
```

### Vega (ν): Sensitivity to Implied Volatility

$$
\nu = S \cdot N'(d_1) \cdot \sqrt{T}
$$

**Same for calls and puts**.

**Note**: Vega is typically expressed per 1% change in IV, so divide by 100.

**C++ Implementation**:
```c++
static double vega(double S, double K, double r, double sigma, double T) {
    double d1_val = BlackScholes::d1(S, K, r, sigma, T);
    return S * BlackScholes::norm_pdf(d1_val) * std::sqrt(T) / 100.0; // Per 1% IV
}
```

### Theta (Θ): Time Decay

**Call Theta**:
$$
\Theta_{\text{call}} = -\frac{S \cdot N'(d_1) \cdot \sigma}{2\sqrt{T}} - r K e^{-rT} N(d_2)
$$

**Put Theta**:
$$
\Theta_{\text{put}} = -\frac{S \cdot N'(d_1) \cdot \sigma}{2\sqrt{T}} + r K e^{-rT} N(-d_2)
$$

**Note**: Theta is typically expressed per day, so divide by 365.

**C++ Implementation**:
```c++
static double call_theta(double S, double K, double r, double sigma, double T) {
    double d1_val = BlackScholes::d1(S, K, r, sigma, T);
    double d2_val = BlackScholes::d2(S, K, r, sigma, T);

    double term1 = -(S * BlackScholes::norm_pdf(d1_val) * sigma) / (2 * std::sqrt(T));
    double term2 = -r * K * std::exp(-r * T) * BlackScholes::norm_cdf(d2_val);

    return (term1 + term2) / 365.0; // Per day
}

static double put_theta(double S, double K, double r, double sigma, double T) {
    double d1_val = BlackScholes::d1(S, K, r, sigma, T);
    double d2_val = BlackScholes::d2(S, K, r, sigma, T);

    double term1 = -(S * BlackScholes::norm_pdf(d1_val) * sigma) / (2 * std::sqrt(T));
    double term2 = r * K * std::exp(-r * T) * BlackScholes::norm_cdf(-d2_val);

    return (term1 + term2) / 365.0; // Per day
}
```

### Rho (ρ): Sensitivity to Interest Rate

**Call Rho**:
$$
\rho_{\text{call}} = K T e^{-rT} N(d_2)
$$

**Put Rho**:
$$
\rho_{\text{put}} = -K T e^{-rT} N(-d_2)
$$

**Note**: Ignored in Phase 1 (short-dated options have minimal rate sensitivity).

---

## Implied Volatility Solver

### Problem Statement

Given:
- Market price of option $C_{\text{market}}$
- Strike $K$, underlying price $S$, time to expiry $T$, rate $r$

Find: $\sigma$ such that $C(\sigma) = C_{\text{market}}$

### Newton-Raphson Method

$$
\sigma_{n+1} = \sigma_n - \frac{C(\sigma_n) - C_{\text{market}}}{\nu(\sigma_n)}
$$

Where $\nu(\sigma)$ is Vega.

**Convergence**: Typically 4-6 iterations for 0.0001 precision.

### C++ Implementation

```c++
class IVSolver {
public:
    static double implied_volatility(
        double market_price,
        double S,
        double K,
        double r,
        double T,
        bool is_call = true,
        double tolerance = 1e-4,
        int max_iterations = 100
    ) {
        // Initial guess: ATM implied volatility rule of thumb
        double sigma = std::sqrt(2 * std::abs(std::log(S / K)) / T);
        sigma = std::clamp(sigma, 0.01, 5.0); // Reasonable bounds

        for (int i = 0; i < max_iterations; ++i) {
            // Calculate option price with current sigma
            double price = is_call
                ? BlackScholes::call_price(S, K, r, sigma, T)
                : BlackScholes::put_price(S, K, r, sigma, T);

            double diff = price - market_price;

            // Check convergence
            if (std::abs(diff) < tolerance) {
                return sigma;
            }

            // Calculate vega
            double vega_val = Greeks::vega(S, K, r, sigma, T) * 100.0; // Remove /100 scaling

            // Avoid division by zero
            if (std::abs(vega_val) < 1e-10) {
                throw std::runtime_error("Vega too small, cannot solve for IV");
            }

            // Newton-Raphson update
            sigma = sigma - diff / vega_val;

            // Ensure sigma stays positive and reasonable
            sigma = std::clamp(sigma, 0.01, 5.0);
        }

        throw std::runtime_error("IV solver did not converge");
    }
};
```

### Edge Cases

| Scenario | Handling |
|----------|----------|
| $C_{\text{market}} < \text{intrinsic value}$ | Return `NaN`, log warning (arbitrage) |
| $T < 0.001$ (< 1 day) | Return historical volatility (IV unreliable) |
| Vega ≈ 0 | Return previous IV, flag as stale |
| Solver diverges | Use bisection method fallback |

---

## Expected Value Calculation

### Formula

$$
EV = (p_{\text{win}} \times g_{\text{avg}}) - (p_{\text{loss}} \times l_{\text{avg}}) - (|\theta| \times t_{\text{hold}})
$$

Where:
- $p_{\text{win}}$ = ML signal strength (e.g., 0.85)
- $p_{\text{loss}}$ = 1 - $p_{\text{win}}$
- $g_{\text{avg}}$ = Average gain if profitable (e.g., 0.50 for +50% take profit)
- $l_{\text{avg}}$ = Average loss if unprofitable (e.g., 0.30 for -30% stop loss)
- $\theta$ = Daily theta (e.g., -0.05 = -$0.05/day)
- $t_{\text{hold}}$ = Expected holding period (days)

### C++ Implementation

```c++
struct EVCalculator {
    double signal_strength;
    double take_profit_target;  // 0.50 = +50%
    double stop_loss_target;    // 0.30 = -30%
    double theta_per_day;       // e.g., -0.05
    int expected_days_held;     // e.g., 3

    double calculate() const {
        double p_win = signal_strength;
        double p_loss = 1.0 - signal_strength;

        double expected_gain = p_win * take_profit_target;
        double expected_loss = p_loss * stop_loss_target;
        double theta_cost = std::abs(theta_per_day) * expected_days_held;

        return expected_gain - expected_loss - theta_cost;
    }
};

// Example usage
EVCalculator ev{
    .signal_strength = 0.85,
    .take_profit_target = 0.50,
    .stop_loss_target = 0.30,
    .theta_per_day = -0.05,
    .expected_days_held = 3
};

double ev_result = ev.calculate();
// ev_result = (0.85 × 0.50) - (0.15 × 0.30) - (0.05 × 3)
//           = 0.425 - 0.045 - 0.15
//           = 0.23 (23% expected return)
```

### Entry Threshold

Only enter trade if:
$$
EV > 0.10 \quad (10\% \text{ minimum expected return})
$$

---

## Position Sizing (Kelly Criterion)

### Full Kelly Formula

$$
f^* = \frac{p \cdot g - (1 - p) \cdot l}{l}
$$

Where:
- $f^*$ = Fraction of capital to risk
- $p$ = Win probability (signal strength)
- $g$ = Average gain per win (e.g., 0.50)
- $l$ = Average loss per loss (e.g., 0.30)

### Fractional Kelly (Conservative)

$$
f_{\text{adj}} = \frac{f^*}{4} \quad (\text{use 1/4 Kelly})
$$

**Rationale**: Full Kelly is aggressive; 1/4 Kelly reduces volatility while preserving growth.

### Position Size Calculation

$$
\text{Position Size} = \min(f_{\text{adj}} \times A, \, 0.05 \times A, \, C_{\text{sector}})
$$

Where:
- $A$ = Account value
- $0.05 \times A$ = Single position limit (5%)
- $C_{\text{sector}}$ = Available sector capacity (15% Mag 7 exposure - current exposure)

### C++ Implementation

```c++
struct KellySizer {
    double win_prob;
    double avg_gain;
    double avg_loss;
    double account_value;
    double current_sector_exposure;
    double max_sector_exposure = 0.15;
    double max_position_pct = 0.05;
    double kelly_fraction = 0.25; // Use 1/4 Kelly

    double calculate_position_value() const {
        // Full Kelly
        double full_kelly = (win_prob * avg_gain - (1 - win_prob) * avg_loss) / avg_loss;

        // Fractional Kelly
        double adj_kelly = full_kelly * kelly_fraction;

        // Kelly-based position size
        double kelly_size = adj_kelly * account_value;

        // Single position limit
        double max_position = max_position_pct * account_value;

        // Sector capacity remaining
        double sector_capacity = (max_sector_exposure * account_value) - current_sector_exposure;

        // Take minimum
        return std::max(0.0, std::min({kelly_size, max_position, sector_capacity}));
    }

    int calculate_contracts(double option_price) const {
        double position_value = calculate_position_value();
        return static_cast<int>(position_value / (option_price * 100.0));
    }
};

// Example
KellySizer sizer{
    .win_prob = 0.85,
    .avg_gain = 0.50,
    .avg_loss = 0.30,
    .account_value = 10000.0,
    .current_sector_exposure = 500.0
};

int contracts = sizer.calculate_contracts(15.35); // Option price = $15.35
// contracts = 3
```

---

## IV Percentile

### Definition

IV Percentile = Rank of current IV within the last $N$ days (typically $N=30$).

$$
\text{IV Percentile} = \frac{\#\{\text{days where IV} < \text{IV}_{\text{current}}\}}{N}
$$

### C++ Implementation

```c++
double calculate_iv_percentile(double current_iv, const std::vector<double>& historical_iv) {
    int count_below = std::count_if(historical_iv.begin(), historical_iv.end(),
        [current_iv](double iv) { return iv < current_iv; });

    return static_cast<double>(count_below) / historical_iv.size();
}

// Example
std::vector<double> iv_history = {0.25, 0.28, 0.30, 0.32, 0.35, 0.38, 0.40};
double current_iv = 0.35;
double percentile = calculate_iv_percentile(current_iv, iv_history);
// percentile = 4/7 ≈ 0.57 (57th percentile)
```

### SQL Implementation (TimescaleDB)

```sql
WITH ranked_iv AS (
    SELECT
        time,
        ticker,
        contract_id,
        opt_iv,
        PERCENT_RANK() OVER (
            PARTITION BY ticker, contract_id
            ORDER BY opt_iv
        ) AS iv_percentile
    FROM market_data_ticks
    WHERE time >= NOW() - INTERVAL '30 days'
      AND ticker = 'NVDA'
      AND contract_id = 123456789
)
SELECT iv_percentile
FROM ranked_iv
WHERE time = (SELECT MAX(time) FROM market_data_ticks WHERE ticker = 'NVDA');
```

---

## Numerical Stability

### Handling Edge Cases

```c++
class SafeMath {
public:
    // Clamp to avoid numerical overflow
    static double safe_exp(double x) {
        return std::exp(std::clamp(x, -700.0, 700.0));
    }

    // Avoid log(0) or log(negative)
    static double safe_log(double x) {
        return std::log(std::max(x, 1e-10));
    }

    // Check for NaN/Inf
    static bool is_valid(double x) {
        return std::isfinite(x);
    }
};
```

### Unit Tests

```c++
TEST(BlackScholesTest, ATMCallPrice) {
    double S = 100.0, K = 100.0, r = 0.05, sigma = 0.20, T = 0.25;
    double price = BlackScholes::call_price(S, K, r, sigma, T);

    EXPECT_NEAR(price, 3.99, 0.01); // Expected ~$4.00
}

TEST(GreeksTest, ATMDelta) {
    double S = 100.0, K = 100.0, r = 0.05, sigma = 0.20, T = 0.25;
    double delta = Greeks::call_delta(S, K, r, sigma, T);

    EXPECT_NEAR(delta, 0.54, 0.01); // ATM call delta ≈ 0.54
}

TEST(IVSolverTest, ConvergesForATM) {
    double S = 100.0, K = 100.0, r = 0.05, T = 0.25;
    double true_sigma = 0.20;
    double market_price = BlackScholes::call_price(S, K, r, true_sigma, T);

    double solved_sigma = IVSolver::implied_volatility(market_price, S, K, r, T, true);

    EXPECT_NEAR(solved_sigma, true_sigma, 1e-4);
}
```

---

## Performance Optimization

### Vectorization (SIMD)

For bulk Greeks calculation:

```c++
#include <immintrin.h>

// Calculate delta for 8 options simultaneously (AVX2)
void calculate_delta_simd(const double* S, const double* K, const double* r,
                         const double* sigma, const double* T,
                         double* delta, int count) {
    for (int i = 0; i < count; i += 4) {
        __m256d s_vec = _mm256_loadu_pd(&S[i]);
        __m256d k_vec = _mm256_loadu_pd(&K[i]);
        // ... continue for all parameters

        // Calculate d1 using AVX2 intrinsics
        // ... (implementation omitted for brevity)

        // Store results
        _mm256_storeu_pd(&delta[i], result);
    }
}
```

### Caching

```c++
struct CachedGreeks {
    double delta, gamma, vega, theta;
    std::chrono::steady_clock::time_point last_update;

    bool is_stale(std::chrono::milliseconds max_age = std::chrono::milliseconds(100)) const {
        auto now = std::chrono::steady_clock::now();
        return (now - last_update) > max_age;
    }
};
```

---

**See Also**:
- [TRADING_STRATEGY.md](TRADING_STRATEGY.md) - How Greeks are used in entry/exit logic
- [ARCHITECTURE.md](ARCHITECTURE.md) - Pricing Engine component
- [API_INTEGRATION.md](API_INTEGRATION.md) - Where market data feeds these calculations

