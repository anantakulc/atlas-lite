# Atlas writing style

The reader is an intelligent generalist who knows economics and business but is **not** a
sector specialist. Write so that person gets it on the first read.

## Rules
1. **One idea per paragraph or bullet.** Length is free. A point can be one line or six, but
   it owns exactly one idea. If a bullet carries two ideas, split it.
2. **Deductive order.** Lead with the conclusion, then support it. Every section and every
   bullet opens with its claim, so the reader can stop early or read on.
3. **No fixed length.** Use judgment: the fewest units that genuinely cover the debate. Don't
   pad to hit a number, don't cut a real point to fit one.
4. **Plain register.** Gloss any sector term in plain language on first use, e.g. "net interest
   margin, the spread a bank earns between what it charges on loans and pays on deposits."
   Explain the mechanism; don't just name the metric.
5. **No em dashes** (voice_clean enforces this mechanically). No AI tells: delve, tapestry,
   crucial, "robust" as filler, hedge stacks like "could potentially." Contractions are fine.
   Active voice.
6. **Concrete over vague.** Numbers carry units and dates. "Margins fell to 7.7% in Q1," not
   "margins came under pressure."

## What Forseti checks
- A bullet that smuggles in two ideas → flag.
- A section that buries its conclusion below the evidence → flag.
- Undefined sector jargon → flag.
