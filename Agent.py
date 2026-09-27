"""
A very small data analyst agent.

What it does, in order:
  1. Python reads the CSV and describes its structure  (no AI involved)
  2. The AI writes pandas code to analyse it           (this is the judgment part)
  3. Python runs that code and collects the numbers    (no AI involved)
  4. The AI reads the numbers and writes a summary     (judgment again)

Run it:  python agent.py sales.csv
"""

import re
import sys
import pandas as pd
import ollama

MODEL = "qwen2.5-coder:7b"
MAX_CHARS = 2000  # never send more than this much result text back to the model


# ---------------------------------------------------------------- step 1
def describe_dataset(df):
    """Plain Python. Builds a short text description of the table's shape."""
    lines = [
        f"Rows: {len(df)}",
        f"Columns: {len(df.columns)}",
        "",
        "Column name | dtype | nulls | unique values",
    ]
    for col in df.columns:
        lines.append(
            f"{col} | {df[col].dtype} | {df[col].isna().sum()} | {df[col].nunique()}"
        )

    lines.append("")
    lines.append("First 2 rows:")
    lines.append(df.head(2).to_string())
    return "\n".join(lines)


# ---------------------------------------------------------------- step 2
CODE_PROMPT = """You are a data analyst. Below is the structure of a pandas DataFrame
called `df`, which is already loaded. pandas is available as `pd`.

{schema}

Write Python code that computes a first-pass analysis of this data.

Hard rules:
- Put your findings in a dictionary called `result`. Nothing else matters.
- Every value must be SMALL: a single number, or a short aggregate with at
  most 10 entries. Aggregate, never enumerate.
- Never put raw rows, customer lists, or per-record output in `result`.
- 4 to 6 findings is right. Pick the ones that would actually tell someone
  something about this business.
- Output only a Python code block. No explanation before or after.

Example of the shape I want:
result = {{
    "total_revenue": float(df["revenue"].sum()),
    "revenue_by_region": df.groupby("region")["revenue"].sum().to_dict(),
}}"""


def ask_for_code(schema):
    reply = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": CODE_PROMPT.format(schema=schema)}],
    )
    return reply["message"]["content"]


def extract_code(text):
    """The model usually wraps code in ```python ... ```. Pull it out."""
    match = re.search(r"```(?:python)?\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text.strip()


# ---------------------------------------------------------------- step 3
def run_code(code, df):
    """
    Runs the AI's code. This is the ONLY place exec() appears in the project.
    If you ever want to sandbox this, you rewrite this one function.
    """
    workspace = {"df": df.copy(), "pd": pd}
    exec(code, workspace)
    if "result" not in workspace:
        raise KeyError("the code ran but never created a variable called 'result'")
    return workspace["result"]


def shrink(result):
    """Safety net. The prompt asks for small output; this enforces it."""
    text = str(result)
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n...[truncated, the result was too large]"
    return text
# ---------------------------------------------------------------- self-correction
MAX_TRIES = 3

RETRY_PROMPT = """The code you wrote failed.

Here is the code:
{code}

Here is the error:
{error}

Rewrite it so it works. Same rules as before: put the findings in a dictionary
called `result`, keep every value small, output only a Python code block."""


def ask_for_retry(code, error):
    reply = ollama.chat(
        model=MODEL,
        messages=[{"role": "user",
                   "content": RETRY_PROMPT.format(code=code, error=error)}],
    )
    return reply["message"]["content"]


def get_working_result(schema, df):
    code = extract_code(ask_for_code(schema))

    for attempt in range(1, MAX_TRIES + 1):
        print(f"\n--- attempt {attempt} of {MAX_TRIES} ---")
        print(code)
        try:
            result = run_code(code, df)
            print(f"\n[ok] ran successfully on attempt {attempt}")
            return result
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            print(f"\n[failed] {error}")
            if attempt == MAX_TRIES:
                raise RuntimeError(f"gave up after {MAX_TRIES} attempts")
            print("[retrying] sending the error back to the model...")
            code = extract_code(ask_for_retry(code, error))


# ---------------------------------------------------------------- step 4
SUMMARY_PROMPT = """These are real numbers computed from a sales dataset:

{findings}

Write 3 or 4 short observations for a data analyst who has not seen this data
yet. Reference the actual figures above. Do not speculate about anything the
numbers do not show. No preamble, just the observations."""


def ask_for_summary(findings):
    reply = ollama.chat(
        model=MODEL,
        messages=[{"role": "user", "content": SUMMARY_PROMPT.format(findings=findings)}],
    )
    return reply["message"]["content"]


# ---------------------------------------------------------------- main
def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "sales.csv"
    df = pd.read_csv(path)

    print(f"\nLoaded {path}\n")

    schema = describe_dataset(df)
    print("--- what Python sees -------------------------------------")
    print(schema)

    result = get_working_result(schema, df)
    findings = shrink(result)
    print(findings)

    print("\n--- what it found ----------------------------------------")
    print(ask_for_summary(findings))
    print()

if __name__ == "__main__":
     main()