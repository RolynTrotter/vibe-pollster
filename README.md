# vibe-pollster

Alex wants to get sound election predictions.

A small, general election-modeling toolkit (`pollster/`) plus a full forecast of
Israel's **27 October 2026 Knesset election** (`israel/`). The modelling borrows
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
| Netanyahu bloc (Likud, Otzma, RZP, Shas, UTJ) | 5% | 58% |
| Bloc + Amcha Yisrael | 10% | 66% |
| Zionist opposition alone | 10% | <1% |
| Opposition + Ra'am | 34% | 1% |
| Opposition + both Arab lists | 86% | 27% |
| Opposition + Shas | 65% | 9% |
| Opposition + Shas + UTJ | 99% | 73% |
| **Neither camp (with Amcha, without Arab lists)** | **74%** | 34% |

Median seats (consensus): Yashar 23, Likud 22, Together 12, Democrats 9,
Yisrael Beytenu 9, UTJ 9, Shas 8, Otzma 8, Joint List 8, RZP 5, Ra'am 5.
Threshold risk: RZP clears it in 88% of runs, Ra'am 78%, Amcha Yisrael 32%,
Hendel's Reservists 32%, Blue and White <1%.

### What moves the result

Each scenario reruns the consensus forecast with the same random draws
(`python -m israel.dynamics`). Change in percentage points:

| Scenario | Bloc+Amcha ≥61 | Opposition ≥61 |
|---|---:|---:|
| Channel 14 & Direct Polls are right | +56 | −10 |
| Polls miss 3 seats toward the right (2015-style) | +16 | −7 |
| Polls miss 3 seats toward the opposition | −8 | +17 |
| 7% of opposition supporters stay home | +8 | −6 |
| 5% of all right-bloc supporters stay home | −5 | +6 |
| 10% of Likud supporters stay home | −4 | +4 |
| Arab turnout falls to 45% (2021 level) | +5 | +5 |
| Arab turnout 67% (KAS projection for a united Joint List) | −5 | −5 |
| Haredi turnout ±8% | ±2 | ∓2 |
| No haredi underpolling correction | −4 | +4 |
| Gevalt: 30% of RZP + Amcha voters switch to Likud | −3 | +4 |
| Amcha drops out (70% Likud / 30% Otzma) | +1 | −2 |
| Fly & Vote expats (25k votes, 75% opposition) | 0 | +1 |

Takeaways:
1. **Deadlock is the modal outcome.** Neither Jewish camp reaches 61 without Arab lists in ~3 of 4 runs.
2. **The pollster split dwarfs everything else.** Channel 14 (Filber/Next Data) and Direct Polls put the bloc ~8 seats above the consensus. Track records don't settle it: after shrinkage, no house's 2015–2022 record is clearly better (bloc-accuracy weights range 0.84–1.15).
3. **Haredi parties hold the balance.** Opposition + Shas + UTJ clears 61 in 99% of runs.
4. **Low Arab turnout helps both Jewish camps** by shrinking the Arab lists; high turnout makes any Jewish majority harder.
5. **Polls have tended to underrate the right**, mostly through the haredi parties (underpolled in 5 of 6 elections, avg 1.4 seats); the model corrects that by default.
6. **A final-week "gevalt" squeeze backfires** for the bloc: it drains RZP and Amcha toward the threshold, wasting votes.

## Method

1. **Polls → vote shares** (`pollster/polls.py`). Seat projections are deflated to vote shares using reported sub-threshold percentages plus 1.5% for unlisted lists.
2. **Weights** (`pollster/weights.py`), per FiveThirtyEight: √n (n capped at 5,000), a 14-day frequency penalty (a house's polls in a window share one poll's weight), and a pollster-quality multiplier.
3. **Average** (`pollster/average.py`): trend + per-house effect, Bayesian-shrunk (prior sd 2.5 pts). The trend blends a Gaussian-kernel local-linear fit and an EWMA, mixed by poll density. Hyperparameters were tuned on 2015–2022 by how well the average at day *t* predicted house-adjusted polls in the next 14 days (538's approach; the surface is flat, MAE 0.544–0.58 pts). "No lean" is set by **anchor weights**: consensus (each house family equal; Direct Polls + Channel 14 share one vote), track record, Channel-14 only, or mainstream only.
4. **Pollster ratings** (`pollster/ratings.py`), per 538's 2024 method: excess error and bloc bias per poll, blended with the same measures relative to other houses in that race, 14%/yr decay, shrinkage n/(n+10), POLLSCORE, and Silver-style "pollster-induced error" weights.
5. **Error model** (`pollster/errors.py`): the backtest average's misses are decomposed into a bloc swing (σ ≈ 1.9 seats on election day, plus 0.10 seats²/day of drift), haredi and Arab family shocks (σ ≈ 1.4, 1.7 seats), and party noise (variance 0.07 + 0.24×seats; ×1.5 for debut lists).
6. **Turnout layer** (`pollster/turnout.py`, `israel/segments.py`): 2022 ballot boxes (CEC) classify the electorate into Arab, Druze, haredi, national-religious core and other Jewish voters (Arab-box turnout comes out at 53.0%, matching the official 53.2%). That segment×party matrix is mapped to 2026 parties and fitted to the current average by iterative proportional fitting. Haredi and Arab shocks are turnout multipliers on those rows, sized so seat errors match the backtest. Scenarios can also remove a share of a party's supporters.
7. **Simulation** (`pollster/simulate.py`) and **seats** (`pollster/systems.py`): 3.25% threshold, Bader-Ofer (D'Hondt) with surplus pairs (Together–YB, Yashar–Democrats, Joint List–Ra'am, Likud–RZP; Shas–UTJ assumed). The allocator reproduces the official 2022 result exactly.

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
python -m israel.build_page         # -> output/knesset_2026.html
python tests/test_allocation.py     # 2022 allocation check
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
