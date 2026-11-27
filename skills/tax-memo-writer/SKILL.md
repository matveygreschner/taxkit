---
name: tax-memo-writer
description: Writes professional U.S. federal tax research memos in Facts / Issue / Analysis / Conclusion form, with authority ranked correctly (Code, regulations, cases and rulings vs. non-binding secondary sources), confidence-level language (more likely than not, substantial authority, reasonable basis) and computations checked with a tax engine. Use this whenever someone asks for a tax memo, client memo, research memo, file memo, position paper or "write up the tax treatment of X", including school assignments (FIAC / IRAC memos). Also use when turning a business tax opportunity scan into a client-ready deliverable. Works with the us-tax-calculator and business-tax-optimizer skills for the numbers when they are installed.
---

# Tax Memo Writer

A tax memo answers one question for a reader who has to act on it: a client, a partner or a
reviewer. Its value comes from three things: getting the issue exactly right, supporting the
answer with the right *weight* of authority, and saying how confident the answer is. This skill
gives the structure and the professional standards. The calculators supply the numbers.

## Structure
Use `assets/memo_template.md`. In brief:

1. **Header**: To, From, Date, Re (one line naming the taxpayer and the question).
2. **Facts**: only the facts that matter to the answer, stated neutrally, with numbers. If you
   assumed a fact, put it in an "Assumptions" line. Wrong or missing facts are the most common
   reason a memo is wrong.
3. **Issue(s)**: each as a single yes/no or how-much question tied to a Code section. For example:
   "Is Mr. Lee's $8,000 loss on selling his personal car deductible under §165(c)?"
4. **Conclusion**: short answers first, one per issue, with a confidence level. Busy readers stop here.
5. **Analysis**: one sub-section per issue:
   - the rule from the highest authority first;
   - how it applies to these facts, including the computation;
   - contrary authority or risks, and why the conclusion still holds;
   - any planning alternative.
6. **Recommendations / next steps**: elections, deadlines, documentation.
7. **Authorities cited**.

A school assignment usually wants one page. A client memo is typically 2-4 pages. Match the
length to the reader.

## Authority and confidence
Read `references/authority.md` before citing anything. The essentials:
- Lead with **primary authority**: the IRC, Treasury regulations (final over temporary over
  proposed), Revenue Rulings and Procedures, and cases (Supreme Court, then circuit, then Tax
  Court regular decisions over memorandum decisions).
- PLRs, IRS publications, form instructions, treatises and articles are **secondary**. They are
  useful to explain or to find primary authority, but they can't be relied on as support.
- Label the conclusion's strength with the standards used for penalties:
  - **will** (~90%+, clear statute or controlling authority on point)
  - **should** (~70%+)
  - **more likely than not** (>50%)
  - **substantial authority** (~40%)
  - **reasonable basis** (~20%, disclosure needed to avoid penalties)

Don't overstate. Conclusions written "will" with only reasonable-basis support are what get
preparers penalized under §6694.
- Cite precisely, for example "IRC §1368(b)(2)", "Treas. Reg. §1.199A-5(c)(2)" or "Rev. Proc. 2025-32 §4.30".
  If you're not sure a citation is exact, say "see generally" or verify it. Never invent a case name or ruling number.

## Numbers
Compute every dollar figure with the us-tax-calculator skill's tax.py script when it's installed.
Its `list` and `describe` commands show the arguments. Use the business-tax-optimizer skill's optimize.py
only for business planning questions, such as entity choice or a list of savings opportunities. Show the computation in the
Analysis as a short table, so the reader can follow and check it. Note the tax year, because many
amounts changed for 2025-2026 under P.L. 119-21 (OBBBA).

## Style
Plain, precise sentences; no hedging adjectives. Use defined short names: "the Company", "Ms.
Jordan". Put dollar amounts in figures, and keep facts in the past tense and law in the present. If facts
are uncertain, give the answer under each alternative instead of picking one silently.
Close with the standard limitation: the memo is based on the facts stated and authority as of
its date.
