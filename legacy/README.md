# Legacy (2023) Tkinter prototype

`ebayAnalysisAgent.py` is the original 2023 prototype, kept for history only. It is not
maintained and does not run against current dependencies:

- It scraped eBay search-result HTML (against eBay's terms of service, and the CSS classes it
  relied on have since changed).
- It called `openai.Completion.create` with `gpt-3.5-turbo-instruct`, an API removed in
  `openai` v1.
- A listing with an unparseable price produced `None`, which crashed `statistics.mean`.

The maintained replacement is the `ebay_comps` package in `src/` (see the top-level README).
