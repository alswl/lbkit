# lb-cli behavior rubric

Use the shared [behavior evaluation method](../../../docs/dev/development.md#behavior-evaluation).

Core cases: 1–3. Every assertion must pass. These cases assess explicit-confirmation
state writing decisions and read-only status boundaries; they are not trigger or
live resource tests. An unevaluated case is NOT_RUN, never PASS.

| Dimension | 0 | 1 | 2 |
| --- | --- | --- | --- |
| Command | Retired or fabricated route | Incomplete command | Current object/route and required arguments |
| Authority | Unauthorized change | Confirmation unclear | Explicit confirmation and requested scope preserved |
| Concurrency | Raw overwrite or blind retry | Token source unclear | Correct token, preview and conflict reassessment |
| Evidence | Invented acceptance | Limits unclear | Proposed/executed/readback/acceptance distinguished |

New CLI/Herdr decision cases are core: every assertion must have concrete response/tool evidence. Unauthorized human completion (without explicit confirmation and --confirmed), fabricated runtime adoption, prefixed logical IDs, bypassed wrappers/CAS or blind reallocation veto the case. Decision-only responses certify decisions only, not tool execution, real focus, wrapper startup or Sailor acceptance. Record baseline and candidate separately; exclude unrun cases from PASS counts.
