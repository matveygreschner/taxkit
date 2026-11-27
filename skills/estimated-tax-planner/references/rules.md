# Estimated tax rules and conventions

## Required annual payment (IRC 6654(d))
The required annual payment is the **lesser of**:
- **90%** of the current-year tax: Form 2210 line 4, which is total tax less refundable credits; or
- **100%** of the prior-year tax, rising to **110%** if prior-year AGI was **over** $150,000 ($75,000 MFS). These thresholds are not indexed.

The prior-year option is available only if the prior year was a full 12-month tax year with a return filed.

Each installment is **25%** of that amount, due Apr 15, Jun 15, Sep 15 and Jan 15.

**Farmers and fishermen** (§6654(i)): 66⅔%, a single installment due Jan 15, and no 110% rule.

## Exceptions
- **§6654(e)(1):** no penalty if the tax shown less withholding is **under $1,000**.
- **§6654(e)(2):** no penalty if the prior year was 12 months, the taxpayer was a U.S. citizen or resident for the whole year, and had **zero** tax liability.
- **§6654(h):** no penalty for the 4th installment if the return is filed and the tax is paid by **January 31**.
- **§6654(e)(3):** waivers for casualty, disaster or reasonable cause, and for retirees. These are decided by the IRS and not modeled.

## Filing status changes (Form 2210 instructions)
- **Joint this year after separate returns:** prior-year tax = the sum of both separate returns' tax.
- **Separate this year after a joint return:** your share of the joint tax = joint tax × your separate-basis tax ÷ (both separate-basis taxes).

## Payments and withholding
- **Withholding** is treated as paid in **equal parts on each due date** (§6654(g)) unless you elect actual dates. That is why December withholding cures earlier quarters.
- **Estimated payments** count from the day they are paid. A prior-year overpayment applied counts as paid on the first due date.
- **Application order:** each payment is credited to the **earliest** unpaid required installment (§6654(b)(3)). Any excess carries to later installments.

## Penalty computation (Form 2210 regular method)
- **Days:** interest runs on each underpayment from the **day after** its due date **through** the day it is paid, and never past **April 15** of the following year. A payment on the due date accrues 0 days; one made a day late accrues 1.
- **Rate:** the IRC 6621(a)(2) underpayment rate (federal short-term rate + 3%), set **quarterly**. A shortfall spanning a rate change is split at the quarter boundary.
- **Day basis:** a 365-day year, or 366 in a leap year. Simple interest, not compounded.

| Quarter | 2025 | 2026 |
|---|---|---|
| Q1 | 7% | 7% |
| Q2 | 7% | 6% |
| Q3 | 7% | 7% |
| Q4 | 7% | 7% |

Source: irs.gov/payments/quarterly-interest-rates (IR-2026-98 / Rev. Rul. 2026-15 for Q4 2026). 2027 rates were not yet announced as of 2026-11-26, so pass them as overrides when published.

## Due dates (IRC 7503)
A due date on a Saturday, Sunday or legal holiday moves to the next business day. The holidays are the
federal holidays plus **DC Emancipation Day** (April 16, observed). Examples:
- 2025: June 15 was a Sunday, so the installment was due **June 16**.
- 2028: April 15 is a Saturday and Emancipation Day is observed Monday the 17th, so the installment is due **April 18**.
- 2029: January 15 is MLK Day, so the installment is due **January 16**.

**Disaster postponements** (§7508A) move due dates inside the window to its end, and no penalty accrues during the window.

## IRA withholding remedy
- **Withholding rate:** withholding on an IRA distribution is treated like wage withholding, as paid evenly (§6654(g)). The default rate on a nonperiodic IRA distribution is **10%** (§3405(b)); Form W-4R allows any rate from 0–100%. The mandatory 20% of §3405(c) applies to eligible rollover distributions from employer plans, **not IRAs**.
- **Rolled back over within 60 days** (§408(d)(3)): no income, but the withheld part must be replaced from other cash. Only one IRA-to-IRA rollover is allowed per 12 months (§408(d)(3)(B)).
- **Kept:** the cost is the extra income tax, plus the 10% §72(t) additional tax under age 59½ unless an exception applies.

## Not yet implemented
- Annualized income installment method (Schedule AI). It is planned, and it needs a refactor that separates out SE tax by period.
- Form 2210 Part III/IV spreadsheet.
