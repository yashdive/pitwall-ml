# Findings (EDA v1, frozen 2026-11-14)

This is the record of EDA v1. Do not change it; the next version gets its own section or file.

What we know about the data. One line each, with where it came from.
Source `02` = `02_raw_race_eda.ipynb`.

## Laps
- One row = one lap of one driver in one race. `(Season, Round, Driver, LapNumber)` is unique. (02, Q1)
- `Round` is only unique within a season. (02, Q1)
- Times are stored as integer nanoseconds. `LapStartDate` is always empty. (02, Q1–Q2)

## Missing lap times
- Few laps have no lap time: mostly safety-car or red-flag laps, plus restart laps after a red flag. (02, Q2, Q4)
- A lap can have a safety car and a red flag at once, so count the two together, not separately. (02, Q2)
- The missing laps are not random (tied to SC/red flag), but harmless: the green-lap filter drops them anyway. (02, Q2)
- Never fill in a missing lap time: it is the target, so the model would learn the fill-in rule. (02, Q2)
- Risk is in neighbour-lap features (previous lap, rolling mean): compute them only over timed laps in the same stint; take tyre age from `TyreLife`, not row counts. (02, Q2)
- Open: for missing laps with no SC or red flag, check if S1 + S2 + S3 can rebuild the lap time. (02, Q2)

## Track status
- A lap's status lists every status during that lap, in order. Many combinations, but only 6 digits: 1 clear, 2 yellow, 4 SC, 5 red, 6 VSC, 7 VSC ending. (02, Q3)
- SC and VSC laps are much slower than green laps; red-flag laps can include the whole stoppage. (02, Q3)
- The first lap after a restart can be green and not a pit lap, but still very slow. Flag it (`is_restart_lap`) and leave it out of degradation. (02, Q4–Q5, Q10)

## Pit stops
- In-lap and out-lap are slow because of the pit stop itself, not tyre wear. (02, Q4)
- Not every pit entry is a stop: under a red flag every car enters the pit lane and may change tyres for free; stops under SC/VSC are cheaper. (02, Q4)

## Tyres
- `Stint` counts tyre sets; `TyreLife` is the age of the current set and resets at each stop. Used sets start older. (02, Q6)
- `"None"` and `"nan"` in `Compound` are text, not missing values. (02, Q6)
- Compound names are per race: Pirelli brings 3 of its compounds and calls them hard / medium / soft for that weekend. The model needs the track as well as the compound. (02, Q10)
- Some stints have no tyre age on any lap. Flag `has_tyre_info` and leave them out of degradation. (02, Q6)
- Some laps have no `Stint`. `groupby` drops them without warning, so check counts with `dropna=False`. (02, Q6)

## Weather
- Track temperature varies little within a race, a lot between races. (02, Q7)
- The rain sensor misses wet tracks (rain before the start). Use the tyre compound to mark wet laps. (02, Q7)
- The track temperature sensor sometimes jumps by 5–15 °C within a minute while nothing else changes. Use only readings from the race itself and treat jumps over 5 °C per minute as errors. (02, Q7)
- v1 uses only track temperature. Each lap gets the last valid reading before the lap started. When predicting a future race, track temperature is an input we choose. (02, Q7)

## Fuel
- Cars get faster every lap as fuel burns, and the size differs by track. Within a stint this hides tyre wear. (02, Q8)
- Correct it per track: `lap time + fuel effect × lap number`. How and why: `fuel_correction.md`. (02, Q8)

## Traffic
- Close behind another car, laps are slower (dirty air). Raw comparisons overstate it because close gaps happen early in the race, when cars are heavy. (02, Q9)

## Degradation
- After cleaning, traffic removal and fuel correction, lap time goes up with tyre age. (02, Q10)
- The rate depends a lot on the track: on HARD about 0.15 s per lap in Bahrain, 0.06 in Melbourne. (02, Q10)
- Some tracks go up in a straight line; others stay flat for a few laps first. Start with a straight line, check later if a curve is needed. (02, Q10)
- Where there are enough stints, softer compounds degrade faster. One race is often too few stints, so the model learns from all races together. (02, Q10)
- Within a stint tyre age and lap number rise together, so any error in the fuel value shifts every degradation rate by the same amount. (02, Q10)

## Model quality references
- Noise floor: even a line fitted through each stint's own laps does not hit every lap; a model that beats it is overfitting or leaking. (computed 2026-10-25)
- Baseline: predict the last laps of a stint as "same as the last few laps". A model must beat this to be worth anything. (computed 2026-10-25)
