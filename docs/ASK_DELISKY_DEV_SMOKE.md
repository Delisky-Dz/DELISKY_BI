# Ask DELISKY DEV smoke — 2026-10-03

The summary-context fix at `21c37be` is confirmed on real
`delisky_bi_dev`, using `config.settings.development`, account
`rachidone1`, and local `qwen3:4b-instruct` for 2026-04-04 through
2026-08-26. This was an in-process Django HTTP smoke, not a browser
rendering test. Neither analytics nor model responses were mocked.

## Confirmed results

- Total sales: `260406534.35 DZD`.
- Sales records: `25095`.
- Visit records / visited: `89588` / `77166`.
- Visit success: `86.13%`.
- Confirmed / possible stopped trucks: `0` / `0`.
- Ask responses used context schema `2`.
- After correction, the analytical and unavailable-profit questions both
  returned HTTP 200 through the full application path with the temporary
  180-second DEV timeout. The profit response only stated the data was
  unavailable; it did not guess or refer to Marketing Helper.
- Both AI tool pages returned HTTP 200 for the manager account.
- Marketing Helper returned three general distribution suggestions and
  explicitly denied access to internal sales when asked for actual totals.

## Follow-up correction

The original 96-token generation budget cut an Arabic analytical answer
mid-sentence, before its limitations. Ask now explicitly requests 256
tokens, with instructions to keep observations short and retain supporting
numbers and limitations. Shared transport defaults and Marketing Helper
are unchanged.

Missing internal metrics must be reported as unavailable rather than
referred to Marketing Helper. Net profit after tax remains unsupported:
the context contains no cost or tax data.

## DEV runtime requirement

The existing 120-second provider timeout produced HTTP 503 for the
analytical question. The complete analytical response passed with a
temporary process-level `ASK_DELISKY_TIMEOUT_SECONDS=180` override.
The response included supported figures and the relevant caveat, and
completed in about 242 seconds end to end (analytics plus inference).

For this local DEV setup, use the 180-second timeout in the DEV process
environment. It has not been persisted into a shared `.env`, installed
into a running service, or applied to Production. A pass with 180 seconds
does not establish reliability with the old 120-second timeout.

## Validation

- Focused assistant and dashboard tests: 126 passed.
- Full project suite: 1170 passed on `test_delisky_bi_dev`.
- Django system checks: passed.
- Regression coverage includes the actual Ollama request budget and the
  prompt boundaries for concise analysis and unavailable internal data.
- No production rollout, provisioning, Waitress/task changes, or merge to
  `main` was performed.
