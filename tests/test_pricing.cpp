#include <gtest/gtest.h>
#include "polyquant/pricing/BlackScholes.h"

using namespace polyquant::pricing;

// Test Case 1: ATM Call Price
// S=100, K=100, r=5%, sigma=20%, T=0.25 (3 months)
// Expected: ~4.61 (Using online calculator)
TEST(BlackScholesTest, ATMCallPrice) {
    double S = 100.0;
    double K = 100.0;
    double r = 0.05;
    double sigma = 0.20;
    double T = 0.25;

    double price = BlackScholes::call_price(S, K, r, sigma, T);

    // Allow small error margin due to approximation
    EXPECT_NEAR(price, 4.61, 0.05);
}

// Test Case 2: ATM Put Price
// Put-Call Parity: C - P = S - K*e^(-rT)
// 4.61 - P = 100 - 100*e^(-0.0125) = 100 - 98.76 = 1.24
// P = 4.61 - 1.24 = 3.37
TEST(BlackScholesTest, ATMPutPrice) {
    double S = 100.0;
    double K = 100.0;
    double r = 0.05;
    double sigma = 0.20;
    double T = 0.25;

    double price = BlackScholes::put_price(S, K, r, sigma, T);

    EXPECT_NEAR(price, 3.37, 0.05);
}

// Test Case 3: Delta Calculation
// ATM Call Delta should be > 0.5 due to drift
TEST(GreeksTest, ATMDelta) {
    double S = 100.0;
    double K = 100.0;
    double r = 0.05;
    double sigma = 0.20;
    double T = 0.25;

    double call_delta = Greeks::call_delta(S, K, r, sigma, T);
    double put_delta = Greeks::put_delta(S, K, r, sigma, T);

    EXPECT_GT(call_delta, 0.50);
    EXPECT_LT(call_delta, 0.60);

    // Put delta = Call delta - 1
    EXPECT_NEAR(put_delta, call_delta - 1.0, 1e-6);
}

// Test Case 4: IV Solver
TEST(IVSolverTest, ConvergesCorrectly) {
    double S = 100.0;
    double K = 100.0;
    double r = 0.05;
    double T = 0.25;
    double target_sigma = 0.25;

    // Calculate theoretical price
    double market_price = BlackScholes::call_price(S, K, r, target_sigma, T);

    // Solve for IV
    double implied_vol = IVSolver::implied_volatility(market_price, S, K, r, T, true);

    EXPECT_NEAR(implied_vol, target_sigma, 1e-4);
}

// Test Case 5: IV Solver Exception
TEST(IVSolverTest, ThrowsOnArbitrage) {
    double S = 100.0;
    double K = 100.0;
    double r = 0.05;
    double T = 0.25;

    // Price lower than intrinsic value (S - K*e^-rT) is impossible
    // Intrinsic = 100 - 98.76 = 1.24
    double impossible_price = 0.50;

    EXPECT_THROW({
        IVSolver::implied_volatility(impossible_price, S, K, r, T, true);
    }, std::runtime_error);
}
