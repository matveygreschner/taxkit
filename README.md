# TaxKit

[![CI](https://github.com/matveygreschner/taxkit/actions/workflows/ci.yml/badge.svg)](https://github.com/matveygreschner/taxkit/actions/workflows/ci.yml)
[![Downloads](https://img.shields.io/github/downloads/matveygreschner/taxkit/total?label=downloads)](https://github.com/matveygreschner/taxkit/releases)

A tested U.S. federal tax engine for 2025 and 2026, under current law after OBBBA. One Python engine computes tax the way the Code and IRS forms do, and drives an Excel and Google Sheets workbook, a business tax opportunity scanner and Claude skills.

## What it covers

- Brackets and capital gains, a full Form 1040, Schedule A and the SALT cap
- Payroll and self-employment tax, credits, kiddie tax
- Basis, property transactions, entities and the dividends received deduction
- MACRS, §179 and bonus depreciation, losses, IRAs and SEPs
- Estimated tax safe harbors and the Form 2210 penalty
- A business scan of 20 planning opportunities, ranked by dollar value with citations

## Quick start

```bash
pip install -r requirements-dev.txt
python -m pytest -q
PYTHONPATH=src python -m taxkit tax 400000 --status S --ltcg 400000
PYTHONPATH=src python -m taxkit.api business_scan "{\"profile\": $(cat examples/acme_s_corp.json), \"format\": \"markdown\"}"
```

## Workbook

[Download TaxKit.xlsx](workbook/TaxKit.xlsx). Opens in Excel or Google Sheets. Pick the year and method on the `Start` sheet. Yellow cells are inputs, green rows are answers. A **Law** method follows the statute and a **Simplified** method shows common hand shortcuts for comparison.

## Skills

| Skill | Download |
|---|---|
| us-tax-calculator | [zip](https://github.com/matveygreschner/taxkit/releases/latest/download/us-tax-calculator.zip) |
| business-tax-optimizer | [zip](https://github.com/matveygreschner/taxkit/releases/latest/download/business-tax-optimizer.zip) |
| estimated-tax-planner | [zip](https://github.com/matveygreschner/taxkit/releases/latest/download/estimated-tax-planner.zip) |
| tax-memo-writer | [zip](https://github.com/matveygreschner/taxkit/releases/latest/download/tax-memo-writer.zip) |

Upload the zip under Settings, Capabilities, Skills, or unzip into `~/.claude/skills/`. Needs Python 3.9+.

## Testing

74 worked problems, hand-checked business and estimated tax cases, and a recalculation of the workbook with an independent formula engine: 1,457 comparisons with 0 mismatches. A Google Sheets round trip matched all 874 formula cells. CI runs on Python 3.10 and 3.13.

## Limits

For planning and learning, not filing. AMT, EITC and education credits are not modeled, and some areas are simplified. Not tax advice.

MIT licensed.
