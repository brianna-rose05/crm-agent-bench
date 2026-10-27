# Do AI Agents Check Their Work?

**A comparative evaluation of five AI models on Salesforce CRM tasks**

This repository holds the code, data and full results behind the study *Do AI Agents Check Their Work? A Comparative Evaluation of Five Models on Salesforce CRM Tasks*.

- **Paper:** [link to Substack post]
- **Full appendix:** [APPENDIX.md](APPENDIX.md) (task list, grading corrections, cost, technical implementation)

Five models worked as CRM agents in a live Salesforce Developer Edition account: Claude Opus 5.5, Claude Sonnet 5.5, Claude Haiku 5.5, GPT-6.1 Sol and DeepSeek V4.1 Flash. Every attempt was graded on what actually changed in the database, not on what the model said it did.

## Results

163 graded attempts per model (Levels 1, 2, 3 and 5), plus 162 Level 4 checks.

| Model | Passed | Level 1 | Level 2 | Level 3 | Level 4 (checks) | Level 5 | Cost per attempt |
|---|---|---|---|---|---|---|---|
| Claude Opus 5.5 | 142 (87%) | 18/18 | 50/50 | 55/55 | 162/162 | 19/40 | 8.4¢ |
| Claude Sonnet 5.5 | 139 (85%) | 18/18 | 49/50 | 52/55 | 162/162 | 20/40 | 3.7¢ |
| DeepSeek V4.1 Flash | 133 (82%) | 18/18 | 45/50 | 48/55 | 162/162 | 22/40 | 0.11¢ |
| Claude Haiku 5.5 | 130 (80%) | 18/18 | 45/50 | 48/55 | 162/162 | 19/40 | 0.19¢ |
| GPT-6.1 Sol | 118 (72%) | 18/18 | 41/50 | 45/55 | 162/162 | 14/40 | 1.1¢ |

- Only three score gaps were statistically significant: Opus and Sonnet over GPT-6.1 Sol, and Sonnet over Haiku.
- Every model reported at least 15 of 20 silently failed saves as completed.
- Models accessed through OpenRouter, October 20 to 22, 2026, at temperature 0.

## The five levels

| Level | Tasks | What it tests | Attempts per task |
|---|---|---|---|
| 1. Everyday work | 1–18 | Single requests: duplicates, pipeline updates, policy and safety | 1 |
| 2. Conversations | 19–28 | A simulated user who gives details slowly, changes their mind or applies pressure | 5 |
| 3. Verify, don't assume | 25, 29–38 | Salesforce quietly changes other fields; stale data; missing records; cut-off tool output | 5 |
| 4. Long jobs | 39–42 | Jobs of 11 to 17 checks, ending in a change report audited against the real changes | 3 |
| 5. Broken tools | 43–50 | Saves that report success without saving, timeouts after saving, partial saves, locks, rate limits | 5 |

## Repository layout

```
run_bench.py          harness: runs models through tasks via OpenRouter
tasks.py              Levels 1–3 tasks and graders
long_tasks.py         Level 4 long jobs
report_audit.py       checks a Level 4 change report against the real changes
faults.py             Level 5 fault layer and outcome classification
tools.py              the eight tools the agent can call
reset.py              wipes the org and reloads the seed data
sf_client.py          Salesforce login (OAuth client-credentials flow)
seed_data/            the fictional company (CSV) and PLANTED.md, which lists every trap
tests/                offline tests: 103 grader checks against a simulated Salesforce
analysis/             combines all runs and computes scores, ranges and re-read rates
results/              one folder per batch: results.csv, meta.json, transcripts/
results/pilots/       pilot runs, not used in the paper's scores
```

### Which results feed the paper

`analysis/combine.py` merges these folders into `analysis/all_runs.csv` (875 graded runs):

| Folder | Contents |
|---|---|
| `top-models`, `cheap-models`, `haiku-full` | Level 1, plus the first Level 2 run for the top models |
| `cheap-multiturn`, `haiku-multiturn`, `level2-extra` | Level 2, runs 1 to 5 |
| `level3-final` | Level 3, 5 runs |
| `level4` | Level 4, 3 runs per job |
| `level5` | Level 5, 5 runs; `manual_review.csv` lists the hand-corrected outcome labels |

Every run has a full transcript in its folder's `transcripts/`: the conversation, every tool call and result, and the before and after state used for grading.

## Reproducing the study

### 1. Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Set up Salesforce

1. Create a free [Salesforce Developer Edition](https://developer.salesforce.com/signup) account.
2. Create an External Client App with the OAuth 2.0 client-credentials flow enabled, and set a "run as" user.
3. Follow [SETUP_SALESFORCE.md](SETUP_SALESFORCE.md) to add the two custom fields and turn off the standard duplicate rules.
4. Copy `.env.example` to `.env` and fill in the app's consumer key and secret, your My Domain and an [OpenRouter](https://openrouter.ai) API key.
5. Check the connection and load the data:

```bash
python test_connection.py
python reset.py
```

### 3. Run

```bash
# find exact model IDs on OpenRouter
python run_bench.py --find claude

# one model, one task
python run_bench.py --models <model-id> --tasks 7

# a full level, 5 runs
python run_bench.py --models <model-id> --suite level3 --runs 5 --out results/my-run
```

Suites: `level1`, `multiturn`, `level3`, `level4`, `level5`, `all`. Runs are resumable: rerun the same command and finished runs are skipped. For Level 4, `--time-budget` saves a checkpoint so a long job can continue where it stopped.

`run_all.sh` is the script used for the final runs.

### 4. Analyze

```bash
python analysis/combine.py     # builds analysis/all_runs.csv
python analysis/stats.py       # scoreboard, 95% ranges, pairwise tests, Level 5 outcomes
python analysis/reread.py      # Level 3 re-read rates
```

### Offline tests

```bash
cd tests
python test_all.py && python test_multiturn.py && python test_level3.py && python test_level4.py && python test_level5.py
```

Each grader must pass a scripted correct agent and fail a scripted agent making the targeted mistake. No Salesforce account or API key is needed.

## Limits

- Developer Edition allows 15,000 Salesforce API calls per day. A typical run uses about 27.
- Total model cost for all graded runs was $27.93.
- Graders are rule-based. Read the transcripts before trusting a surprising score.

## Citation

> Pischke, B. (2026). *Do AI Agents Check Their Work? A Comparative Evaluation of Five Models on Salesforce CRM Tasks.* [link]
