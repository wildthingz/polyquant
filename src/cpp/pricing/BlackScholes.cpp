#include "polyquant/pricing/BlackScholes.h"
#include <cmath>
#include <algorithm>
#include <stdexcept>

namespace polyquant {
namespace pricing {

// Standard normal CDF (Abramowitz & Stegun approximation)
double BlackScholes::norm_cdf(double x) {
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
double BlackScholes::norm_pdf(double x) {
    static const double inv_sqrt_2pi = 0.3989422804014327;
    return inv_sqrt_2pi * std::exp(-0.5 * x * x);
}

// Calculate d1
double BlackScholes::d1(double S, double K, double r, double sigma, double T) {
    return (std::log(S / K) + (r + 0.5 * sigma * sigma) * T) / (sigma * std::sqrt(T));
}

// Calculate d2
double BlackScholes::d2(double S, double K, double r, double sigma, double T) {
    return d1(S, K, r, sigma, T) - sigma * std::sqrt(T);
}

// Call option price
double BlackScholes::call_price(double S, double K, double r, double sigma, double T) {
    if (T <= 0) return std::max(S - K, 0.0);

    double d1_val = d1(S, K, r, sigma, T);
    double d2_val = d2(S, K, r, sigma, T);

    return S * norm_cdf(d1_val) - K * std::exp(-r * T) * norm_cdf(d2_val);
}

// Put option price
double BlackScholes::put_price(double S, double K, double r, double sigma, double T) {
    if (T <= 0) return std::max(K - S, 0.0);

    double d1_val = d1(S, K, r, sigma, T);
    double d2_val = d2(S, K, r, sigma, T);

    return K * std::exp(-r * T) * norm_cdf(-d2_val) - S * norm_cdf(-d1_val);
}

// Greeks Implementation

double Greeks::call_delta(double S, double K, double r, double sigma, double T) {
    double d1_val = BlackScholes::d1(S, K, r, sigma, T);
    return BlackScholes::norm_cdf(d1_val);
}

double Greeks::put_delta(double S, double K, double r, double sigma, double T) {
    return call_delta(S, K, r, sigma, T) - 1.0;
}

double Greeks::gamma(double S, double K, double r, double sigma, double T) {
    double d1_val = BlackScholes::d1(S, K, r, sigma, T);
    return BlackScholes::norm_pdf(d1_val) / (S * sigma * std::sqrt(T));
}

double Greeks::vega(double S, double K, double r, double sigma, double T) {
    double d1_val = BlackScholes::d1(S, K, r, sigma, T);
    return S * BlackScholes::norm_pdf(d1_val) * std::sqrt(T) / 100.0; // Per 1% IV
}

double Greeks::call_theta(double S, double K, double r, double sigma, double T) {
    double d1_val = BlackScholes::d1(S, K, r, sigma, T);
    double d2_val = BlackScholes::d2(S, K, r, sigma, T);

    double term1 = -(S * BlackScholes::norm_pdf(d1_val) * sigma) / (2 * std::sqrt(T));
    double term2 = -r * K * std::exp(-r * T) * BlackScholes::norm_cdf(d2_val);

    return (term1 + term2) / 365.0; // Per day
}

double Greeks::put_theta(double S, double K, double r, double sigma, double T) {
    double d1_val = BlackScholes::d1(S, K, r, sigma, T);
    double d2_val = BlackScholes::d2(S, K, r, sigma, T);

    double term1 = -(S * BlackScholes::norm_pdf(d1_val) * sigma) / (2 * std::sqrt(T));
    double term2 = r * K * std::exp(-r * T) * BlackScholes::norm_cdf(-d2_val);

    return (term1 + term2) / 365.0; // Per day
}

// IV Solver Implementation

double IVSolver::implied_volatility(
    double market_price,
    double S,
    double K,
    double r,
    double T,
    bool is_call,
    double tolerance,
    int max_iterations
) {
    // Initial guess: ATM implied volatility rule of thumb
    double sigma = 0.5; // Default to 50%

    // If not ATM, use the approximation
    if (std::abs(S - K) > 1e-4) {
        sigma = std::sqrt(2 * std::abs(std::log(S / K)) / T);
    }

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
            // If vega is too small, Newton-Raphson fails.
            // This happens deep ITM/OTM.
            // Fallback: Simple bisection step or just break if we are close enough
            if (std::abs(diff) < tolerance * 10) return sigma; // Accept loose convergence

            // Perturb sigma slightly to try to escape flat region
            sigma += 0.01;
            continue;
        }

        // Newton-Raphson update
        sigma = sigma - diff / vega_val;

        // Ensure sigma stays positive and reasonable
        sigma = std::clamp(sigma, 0.01, 5.0);
    }

    throw std::runtime_error("IV solver did not converge");
}

} // namespace pricing
} // namespace polyquant
