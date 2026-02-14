#pragma once

#include <cmath>
#include <algorithm>
#include <stdexcept>

namespace polyquant {
namespace pricing {

class BlackScholes {
public:
    // Standard normal CDF
    static double norm_cdf(double x);

    // Standard normal PDF
    static double norm_pdf(double x);

    // Calculate d1
    static double d1(double S, double K, double r, double sigma, double T);

    // Calculate d2
    static double d2(double S, double K, double r, double sigma, double T);

    // Call option price
    static double call_price(double S, double K, double r, double sigma, double T);

    // Put option price
    static double put_price(double S, double K, double r, double sigma, double T);
};

class Greeks {
public:
    static double call_delta(double S, double K, double r, double sigma, double T);
    static double put_delta(double S, double K, double r, double sigma, double T);

    static double gamma(double S, double K, double r, double sigma, double T);

    static double vega(double S, double K, double r, double sigma, double T);

    static double call_theta(double S, double K, double r, double sigma, double T);
    static double put_theta(double S, double K, double r, double sigma, double T);
};

class IVSolver {
public:
    static double implied_volatility(
        double market_price,
        double S,
        double K,
        double r,
        double T,
        bool is_call,
        double tolerance = 1e-4,
        int max_iterations = 100
    );
};

} // namespace pricing
} // namespace polyquant
