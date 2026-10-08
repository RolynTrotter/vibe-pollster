# vibe-pollster

Alex wants to get sound election predictions.

A general election-modeling toolkit (`pollster/`), tested blind on 23 elections in six
countries (`countries/`), plus a full forecast of Israel's **27 October 2026 Knesset
election** (`israel/`). The modelling borrows
from FiveThirtyEight's published methods (poll weighting, house effects, pollster
ratings, tuned averages, correlated-error simulation) and from Skipper Seabold's
replication of the 2012 Silver model ([jseabold/538model](https://github.com/jseabold/538model)).
It adds what a multiparty, threshold-PR system needs: seat-to-vote conversion,
Bader-Ofer allocation with surplus agreements, and a turnout layer for the groups
whose turnout swings Israeli elections.

**Interactive results page:** built to `output/knesset_2026.html` (also published as a
private Claude artifact, "Knesset 2026 Forecast").

## Forecast as of 7 October 2026 (20 days out)

20,000 simulated elections from 37 polls by 8 houses published since the lists were set (5 Sep).

| Path to 61 seats | Consensus | If Channel 14 & Direct Polls are right |
|---|---:|---:|
| Netanyahu bloc (Likud, Otzma, RZP, Shas, UTJ) | 4% | 50% |
| Bloc + Amcha Yisrael | 9% | 60% |
| Zionist opposition alone | 11% | <1% |
| Opposition + Ra'am | 37% | 2% |
| Opposition + both Arab lists | 87% | 33% |
| Opposition + Shas | 69% | 14% |
| Opposition + Shas + UTJ | 98% | 70% |
| **Neither camp (with Amcha, without Arab lists)** | **73%** | 40% |

Median seats (consensus): Yashar 22, Likud 22, Together 12, Democrats 9,
Yisrael Beytenu 9, Shas 9, UTJ 8, Otzma 8, Joint List 8, RZP 6, Ra'am 5.
Threshold risk: RZP clears it in 89% of runs, Ra'am 81%, Hendel's Reservists 38%,
Amcha Yisrael 37%, Blue and White <1%.

### What moves the result

Each scenario reruns the consensus forecast with the same random draws
(`python -m israel.dynamics`). Change in percentage points:

| Scenario | Bloc+Amcha ≥61 | Opposition ≥61 |
|---|---:|---:|
| Channel 14 & Direct Polls are right | +51 | −11 |
| Polls miss 3 seats toward the right (2015-style) | +15 | −8 |
| Polls miss 3 seats toward the opposition | −7 | +17 |
| 7% of opposition supporters stay home | +7 | −7 |
| 5% of all right-bloc supporters stay home | −4 | +6 |
| 10% of Likud supporters stay home | −3 | +4 |
| Arab turnout falls to 45% (2021 level) | +5 | +5 |
| Arab turnout 67% (KAS projection for a united Joint List) | −5 | −5 |
| Haredi turnout ±8% | ±2 | ∓2 |
| No Shas underpolling correction | −2 | +2 |
| Gevalt: 30% of RZP + Amcha voters switch to Likud | −2 | +4 |
| Amcha drops out (70% Likud / 30% Otzma) | +1 | −2 |
| Fly & Vote expats (25k votes, 75% opposition) | 0 | +1 |

Takeaways:
1. **Deadlock is the modal outcome.** Neither Jewish camp reaches 61 without Arab lists in ~3 of 4 runs.
2. **The pollster split dwarfs everything else.** Channel 14 (Filber/Next Data) and Direct Polls put the bloc ~8 seats above the consensus. Track records don't settle it: after shrinkage, no house's 2015–2022 record is clearly better.
3. **Haredi parties hold the balance.** Opposition + Shas + UTJ clears 61 in 98% of runs.
4. **Low Arab turnout helps both Jewish camps** by shrinking the Arab lists; high turnout makes any Jewish majority harder.
5. **Polls keep underrating Shas** (5 of 6 elections, avg 1.1 seats), not haredim generally: UTJ's average was on target. The model corrects Shas by default.
6. **A final-week "gevalt" squeeze backfires** for the bloc: it drains RZP and Amcha toward the threshold, wasting votes.

## Backtest: how close would it have been?

`python -m israel.backtest` holds out each of the six elections in turn, re-learns pollster ratings, error sizes and the Shas correction from the other five, and forecasts the held-out election under its real rules (its own surplus agreements; the allocator reproduces all six official results).

| Election | Bloc, 20 days out (80% range) | Bloc, final polls | Raw poll avg | Actual | P(bloc ≥61), final |
|---|---|---|---:|---:|---:|
| 2015 | 59.9 (54–66) | 57.6 (52–63) | 56.4 | 57 | 26% |
| Apr 2019 | 63.9 (57–71) | 64.9 (58–72) | 64.7 | 65 | 80% ✓ |
| Sep 2019 | 57.8 (51–65) | 59.6 (53–66) | 58.5 | 55 | 43% |
| 2020 | 56.7 (51–63) | 58.4 (53–64) | 57.2 | 58 | 32% |
| 2021 | 47.9 (41–55) | 52.4 (45–60) | 50.5 | 52 | 7% |
| 2022 | 63.0 (56–70) | 63.5 (57–70) | 60.3 | 64 | 71% ✓ |

- **Bloc size:** average miss 1.1 seats from the final polls (raw poll average 1.7) and 2.2 from 20 days out (raw 2.5). Actual inside the 80% range in 6 of 6 at both horizons, so ranges may be slightly wide.
- **Bloc ≥61:** Brier score 0.08 (raw polls read as yes/no: 0.17; they called 2022 wrong).
- **Party by party:** no better than the polls, average miss 1.7 seats vs 1.6. The big misses were shared by every pollster: Likud 2015 (polled ~21, won 30, mostly Jewish Home voters switching, so the bloc was still right) and New Right and Zehut in April 2019 (polled at 5–6 seats, both missed the threshold).
- **Threshold calls** (lists with a 3–97% chance): Brier 0.14 from the final polls, about the same as raw polls; 0.15 vs 0.27 from 20 days out.
- Caveat: averaging hyperparameters were tuned once on all six elections (flat surface, little leakage). Writing this backtest also exposed two fixes now in the model: Shas, not haredim generally, is what polls miss, and seat-to-share conversion was understating 4–5 seat lists.

## General-purpose forecaster: six countries, 23 elections

The Israeli model is one instance of a country-agnostic pipeline (`pollster/pipeline.py`,
`pollster/forecast.py`). Any election decided by a national party-list vote with a
threshold can be forecast from a short spec and a polls CSV:

```bash
python -m pollster.forecast examples/israel_2026_spec.json examples/israel_2026_polls.csv --run-date 2026-10-07
```

**Countries configured** (`countries/`): Germany 2013–2025, Netherlands 2017–2025, Sweden
2014–2022, Denmark 2015–2022, New Zealand 2017–2023, plus Israel 2015–2022. Polls and
results are parsed from Wikipedia snapshots by a generic parser (`pollster/wiki.py`) with
per-country party aliases, then checked against ParlGov. Seat rules: D'Hondt, Sainte-Laguë,
modified Sainte-Laguë, Hare largest remainder, thresholds, surplus agreements and
threshold exemptions (`pollster/systems.py`; `tests/test_systems.py` checks them against
official seat counts).

**Blind backtest** (`python -m countries.backtest && python -m countries.scorecard`): each
election is forecast with error parameters fitted on all the *other* elections. Results
(published as the "Election Model Scorecard" artifact; `output/scorecard.html`):

| 20 days out | Vote miss / list | 80% ranges hold | Brier: threshold | Brier: largest list | Brier: majorities |
|---|---:|---:|---:|---:|---:|
| Full model | 1.39 pts | 80% | 0.101 | 0.292 | 0.089 |
| Unseen country (no own history) | 1.39 | 85% | 0.103 | 0.299 | 0.093 |
| Generic cross-national error size | 1.41 | 95% | 0.131 | 0.288 | 0.101 |
| Plain poll average + generic error | 1.42 | 94% | 0.131 | 0.302 | 0.104 |
| Polls read as certain | 1.41 | – | 0.141 | 0.609 | 0.227 |

From the final polls the full model misses by 1.02 pts per list (plain average 1.03), with
Brier 0.082 / 0.216 / 0.078 against 0.105 / 0.348 / 0.114 for reading the polls as certain.

What this shows:
- **Point estimates can't beat a plain poll average**; house adjustments barely move it when there are several pollsters.
- **Probabilities are where the value is**: who comes first and who gets a majority are scored far better than by reading polls at face value.
- **Correctly sized error is most of that value.** Error sizes fitted on these elections give honest 80% ranges three weeks out; a generic cross-national size is too wide and calls thresholds worse. On the final polls all variants are close.
- **It transfers**: forecasting a country with nothing learned from its own past works as well as the full model, so a new list-PR country only needs a config file.
- **Late swings remain unforecastable**: the Dutch PVV (2023) and D66 (2025) won with near-zero odds three weeks out.
- Calibration is decent and, if anything, slightly cautious (events given 60–80% happened about 70–90% of the time).

**Cross-national check.** `countries/jw_prior.py` fits error sizes to Jennings & Wlezien's
archive (poll-of-polls vs results, 129 legislative elections in 31 countries since 1990;
[doi:10.7910/DVN/8421DX](https://doi.org/10.7910/DVN/8421DX)). Election-day party error
agrees with this backtest (sd ≈ 1.5 pts for a 10% party, 2.3 for a 30% party); the six
countries here poll better than the archive average further out. The 292 MB source file
is not in the repo; download it from Dataverse to refit `data/processed/multi/jw_prior.json`.

**Not covered yet:** district systems (FPTP: UK, Canada, US House), presidential runoffs,
and regional list systems such as Spain's.

## Method

1. **Polls → vote shares** (`pollster/polls.py`). Seat projections are deflated to vote shares using reported sub-threshold percentages plus 1.5% for unlisted lists; seat-winning lists share the rest in proportion to seats + 0.5 (undoing D'Hondt's big-list tilt) and are never put below the threshold.
2. **Weights** (`pollster/weights.py`), per FiveThirtyEight: √n (n capped at 5,000), a 14-day frequency penalty (a house's polls in a window share one poll's weight), and a pollster-quality multiplier.
3. **Average** (`pollster/average.py`): trend + per-house effect, Bayesian-shrunk (prior sd 2.5 pts). The trend blends a Gaussian-kernel local-linear fit and an EWMA, mixed by poll density. Hyperparameters were tuned on 2015–2022 by how well the average at day *t* predicted house-adjusted polls in the next 14 days (538's approach; the surface is flat, MAE 0.544–0.58 pts). "No lean" is set by **anchor weights**: consensus (each house family equal; Direct Polls + Channel 14 share one vote), track record, Channel-14 only, or mainstream only.
4. **Pollster ratings** (`pollster/ratings.py`), per 538's 2024 method: excess error and bloc bias per poll, blended with the same measures relative to other houses in that race, 14%/yr decay, shrinkage n/(n+10), POLLSCORE, and Silver-style "pollster-induced error" weights.
5. **Error model** (`pollster/errors.py`): the backtest average's misses are decomposed into a bloc swing (σ ≈ 1.7 seats on election day, plus 0.11 seats²/day of drift), haredi and Arab family shocks (σ ≈ 1.4, 1.6 seats), party noise (variance 0.05 + 0.31×seats; ×1.5 for debut lists), and persistent party bias (applied to Shas only: +1.1 seats).
6. **Turnout layer** (`pollster/turnout.py`, `israel/segments.py`): 2022 ballot boxes (CEC) classify the electorate into Arab, Druze, haredi, national-religious core and other Jewish voters (Arab-box turnout comes out at 53.0%, matching the official 53.2%). That segment×party matrix is mapped to 2026 parties and fitted to the current average by iterative proportional fitting. Haredi and Arab shocks are turnout multipliers on those rows, sized so seat errors match the backtest; they carry no mean shift. Scenarios can also remove a share of a party's supporters.
7. **Simulation** (`pollster/simulate.py`) and **seats** (`pollster/systems.py`): 3.25% threshold, Bader-Ofer (D'Hondt) with surplus pairs (Together–YB, Yashar–Democrats, Joint List–Ra'am, Likud–RZP; Shas–UTJ assumed). The allocator reproduces all six official results, 2015–2022, exactly.

### What was borrowed, and what wasn't

From 538/Silver: recency/sample-size/frequency weighting, effective-sample thinking, house effects with shrinkage, pollster ratings (excess error, relative-to-race adjustment, shrinkage, POLLSCORE), averages tuned on future-poll prediction, correlated simulation. Not borrowed: US fundamentals (economy, incumbency, demographics regression) and state-level correlation, which have no Israeli analogue in a single national list vote; the turnout segments play that role instead.

### Survey inputs (IDI and others)

- **IDI Israeli Voice Index** (Aug 2026, fieldwork 31 Aug–3 Sep; Jul 2026; May/Jun 2026), PDFs in `data/raw/idi/`: 8.7% of Arabs vs 1.2% of Jews say they don't intend to vote; Oct 7 is a central vote factor for ~two-thirds of Jews but only about a quarter of haredim; 61% oppose Ra'am in government (July). IDI Democracy Index 2025: 43% of right-wing Jews say voting makes no difference (15% on the left). These set the ranges for the stay-home scenarios and the coalition paths shown. IDI microdata (dataisrael.idi.org.il) was not reachable from the build environment.
- **Konrad Adenauer Program survey of Arab citizens** (May 2026): expected Arab turnout ~53%, ~67% with a united Joint List.

## Run it

```bash
pip install -r requirements.txt
python -m israel.scrape_meforum data/raw/polls/meforum_polls_2026-10-07.html  # -> polls_2026.csv
python -m israel.backtest_data      # 2015-2022 polls and results
python -m israel.segments           # 2022 ballot-box segments
python -m israel.calibrate          # ratings, error model (--retune to redo the grid, ~5 min)
python -m israel.forecast           # -> output/forecast.json
python -m israel.dynamics           # -> output/dynamics.json
python -m israel.backtest           # -> output/backtest.json (leave-one-election-out)
python -m israel.build_page         # -> output/knesset_2026.html
python tests/test_allocation.py     # 2022 allocation check
python tests/test_systems.py        # seat rules vs official results in other countries

# cross-country
python -m countries.ingest          # Wikipedia snapshots -> data/processed/multi/
python -m countries.backtest        # leave-one-election-out, 4 variants (~10 min)
python -m countries.scorecard && python -m countries.build_scorecard   # -> output/scorecard.html
node tests/js_parity.js output/knesset_2026.html   # browser simulator matches Python
```

To refresh with new polls: `curl -sSL https://israelvote.meforum.org/polls/ -o data/raw/polls/meforum_polls_$(date +%F).html`, scrape that file, then rerun from `israel.forecast` with `--run-date`. Polls can't be published after Friday 23 Oct.

## Using the toolkit for another election

`pollster/` has no Israel-specific code. You need: a long poll table (`date, pollster, party, share, n`), past polls + results for calibration, a family map for correlated errors, optional segment composition, and an electoral system (`ListPR` covers list PR with thresholds and apparentment; add others in `systems.py`).

## Caveats

Six backtest elections is a small sample; every error parameter is uncertain. The ballot-box segment method is ecological. The surplus agreement list may change until the 16 Oct deadline. A statistical illustration, not a prediction of who will govern.

## Sources

- Polls: [Middle East Forum Israel poll archive](https://israelvote.meforum.org/polls/)
- Backtest: Wikipedia "Opinion polling for the 2015 / April 2019 / September 2019 / 2020 / 2021 / 2022 Israeli legislative election" and the corresponding election articles (snapshots in `data/raw/backtest/`)
- 2022 ballot-box results: [Central Elections Committee](https://votes25.bechirot.gov.il/)
- [IDI Israeli Voice Index](https://en.idi.org.il/), Aug/Jul/Jun/May 2026
- FiveThirtyEight: [pollster ratings data](https://github.com/fivethirtyeight/data/tree/master/pollster-ratings), "How 538's pollster ratings work" (2024), "How our polling averages work" (2023)
- Stoetzer et al. (2019), "Forecasting Elections in Multiparty Systems", *Political Analysis* 27(2)
