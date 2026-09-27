# Local Data Analyst Agent

An agent that reads a CSV, writes its own pandas code to analyse it, runs that code,
and reports what it found — entirely on a laptop, with no API keys and no data
leaving the machine.

Built with Python, pandas, and a 7B model running locally through [Ollama](https://ollama.com).

---

## What it does

```
1.  Python reads the CSV                      (deterministic)
2.  Python extracts the schema                (deterministic)
3.  LLM writes pandas code to analyse it      (judgment)
4.  Python executes that code                 (deterministic)
       └─ on error: hand the traceback back, retry (max 3)
5.  LLM turns the resulting numbers into prose (judgment)
```

The model is called twice on a clean run, and once more per failed attempt.

---

## The design rule

**The LLM is used only where judgment is required. Everything deterministic stays in Python.**

This sounds obvious and is easy to violate. An early version was going to ask the
model to describe the dataset's structure — but column names, dtypes and null counts
are things pandas already knows exactly. Asking a language model to report them
introduces the possibility of a wrong answer in exchange for nothing.

The same rule is why `exec()` lives in exactly one function, `run_code()`. Isolating
it means sandboxing later is a single-function rewrite rather than an audit.

---

## Self-correction

Generated code fails often, usually in dull ways — a capitalised column name, a
method that doesn't exist on that dtype. Rather than crashing, the agent catches the
exception, formats it as text, and sends it back to the model with the code that
produced it:

```
--- attempt 1 of 3 ---
result = df["Revenue"].sum()

[failed] KeyError: 'Revenue'
[retrying] sending the error back to the model...

--- attempt 2 of 3 ---
result = {"total_revenue": float(df["revenue"].sum())}

[ok] ran successfully on attempt 2
```

Attempts are capped at three. A model stuck on an error it cannot fix will loop
indefinitely otherwise.

---

## Known limitation: the model cannot be trusted to compare numbers

This is the most interesting failure in the project, and it is still present.

The agent computes correct figures and then describes them incorrectly. Real output
from a recent run:

**Computed by pandas (correct):**

```
revenue_by_region: {'East': 48093, 'North': 60358, 'South': 35073, 'West': 57170}
```

**Written by the model:**

> The East region has the highest revenue at $48,093, followed by the North at $60,358.

East is the **lowest** of the four. North is the highest. The model also says
"followed by" while quoting a larger number immediately after.

The cause looks structural rather than random: the dictionary arrives in alphabetical
order, and the model treats first-listed as largest. It reproduced across separate
sessions.

Two things worth noting:

- **The `try`/`except` loop cannot catch this.** The code ran perfectly. There is no
  exception. Only a human reading the sentence can tell it is false. Self-correction
  handles crashes, not falsehoods.
- **The model was given two jobs** — compare the numbers, then write a sentence about
  them. It is good at the second and unreliable at the first.

**Planned fix:** remove the first job. A `to_facts()` function will sort every
breakdown in Python and hand the model pre-resolved statements —
`highest is North at 60,358`, `lowest is South at 35,073` — with an instruction not to
reorder or recalculate anything. The model's only remaining task becomes phrasing.

This is the same design rule as above, applied to a place where I had originally
missed it.

---

## Running it

Requires Python 3.11 and [Ollama](https://ollama.com).

```bash
ollama pull qwen2.5-coder:7b

pip install -r requirements.txt

python makeData.py        # generates sales.csv (600 rows, synthetic)
python Agent.py sales.csv
```

`sales.csv` is generated data with a fixed random seed. It contains no real
information about anyone.

Note on memory: the 7B model needs roughly 5GB of free RAM. On an 8GB machine it
loads, but with little headroom — `qwen2.5-coder:3b` is a reasonable swap if it fails
to allocate.

---

## Files

| File | Purpose |
|---|---|
| `Agent.py` | The agent. Pipeline, prompts, retry loop. |
| `makeData.py` | Generates the synthetic dataset. |
| `sales.csv` | 600 rows of fake sales data. |
| `requirements.txt` | Dependencies. |

---

## Deliberate constraints

- **Fully local.** No API keys, no accounts, no cost. Nothing is uploaded anywhere.
  Running this on a hosted notebook would be easier and would make that claim untrue.
- **Metadata only.** The model sees the schema and two sample rows, never the full
  dataset. Token cost stays flat as the CSV grows.
- **A fixed pipeline, not an open-ended loop.** The model does not decide how many
  steps it needs. This is more reliable and less impressive, and that trade was made
  knowingly.

---

## Roadmap

- [ ] `to_facts()` — resolve comparisons in Python before the summary step
- [ ] Streamlit interface
- [ ] Evaluation set: ~20 questions with known answers, measuring first-attempt and
      post-correction accuracy
- [ ] Sandbox the `exec()` call
- [ ] User-supplied questions rather than automatic analysis only

---

## Honest scope

This is a learning project. `exec()` is not sandboxed and should not be pointed at
untrusted input. It is built for small CSVs on one machine. A 7B model is weak at
interpreting numbers, which is the subject of the limitation section above.
