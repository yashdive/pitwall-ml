# Fuel correction

## The problem
During a race two things change every lap:
- **Tyres wear** → laps get slower.
- **Fuel burns** (no refuelling in F1) → the car gets lighter → laps get faster.

Both happen at the same time, so raw lap times show only their difference. Tyre wear looks smaller than it is.

## Notation
| Symbol | Meaning |
|---|---|
| `n` | race lap number |
| `a` | tyre age in laps (`TyreLife`); resets at each pit stop |
| `t(n)` | observed lap time on lap `n` |
| `d` | degradation: seconds lost per lap of tyre age |
| `f` | fuel effect: seconds gained per race lap as fuel burns |
| `t₀` | base pace of this car on this track |

Simple model of a clean lap:

    t(n) = t₀ + d·a − f·n + noise

## Why raw times hide degradation
Within a stint, tyre age and lap number both go up by 1 every lap. So from one lap to the next:

    change in lap time = d − f

The observed slope is `d − f`, not `d`.

Example with `d = 0.18`, `f = 0.06` over a 15-lap stint:
- observed rise: 15 × (0.18 − 0.06) = **1.8 s**
- real tyre loss: 15 × 0.18 = **2.7 s**
- fuel hid **0.9 s** of wear.

## The correction
Add back the time the fuel gave the car:

    t_corr(n) = t(n) + f·n  =  t₀ + d·a + noise

Now the lap time only rises with tyre age, and the slope of `t_corr` against `a` is `d`.
Every lap is compared as if the car carried the same fuel as at the start.

## How `f` is estimated
Tyre age resets at each pit stop; lap number does not. That lets us separate the two:
- **Quick way:** compare the first laps of consecutive stints (tyres are new again, fuel is not).
  VER, Bahrain 2022: 98.27 → 97.40 s over 14 laps → f ≈ 0.06 s/lap.
- **Proper way:** per race, fit `t = t₀ + d·a − f·n` (plus compound and driver terms) on clean laps.

## Typical values (2022–2025, clean laps)
- Median across races: **f ≈ 0.056 s/lap**
- Low: Monaco ~0.03, Spielberg ~0.03 · High: Spa ~0.08, Suzuka ~0.08 · Bahrain ~0.07–0.08
- Longer laps burn more fuel per lap, so `f` per lap is larger.

## Things to remember
- **An error in `f` moves `d` one-for-one.** If `f` is 0.015 too low, every degradation rate comes out 0.015 too low.
- `f` also includes **track evolution** (the track getting faster as rubber builds up). Both grow with lap number and can't be separated from race data. Treat `f` as the "race-progress effect".
- `f` is **per track**: stored in `configs/tracks/<circuit>.yaml` (D13), not one global number.

## Where it is used
Feature layer, before fitting degradation:

    lap_time_fuel_corrected = lap_time + f_track × LapNumber
