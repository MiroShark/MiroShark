"""Build structured infographic slide plans from a researched decision tree.

This module is intentionally deterministic. The app should do the policy
understanding and fact selection before any image model is called; the image
model receives narrow slide briefs plus exact labels/facts to render.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .education_planner import plan_education_sequence
from .normalization_engine import build_normalized_comparison
from .fact_packs.australia_budget import normalization_inputs_for_tax_per_resident

MAX_FACT_CHARS = 170
MAX_PROMPT_FACTS = 6
STYLE_PRESET = (
    "clean hand-drawn sketchnote infographic on a warm white background; "
    "black marker outlines; simple doodle icons; chunky arrows connecting ideas; "
    "limited accent colors only (teal, orange, yellow); lots of whitespace; "
    "friendly educational tone; cleaner and less busy than a workshop whiteboard; "
    "no photorealism, no dense paragraphs, no tiny text"
)

STYLE_PREPROMPT = (
    "Visual style guide: Make this look like a clean explanatory sketchnote/whiteboard infographic, "
    "inspired by hand-drawn learning maps but more minimal and polished. Use a white or warm off-white "
    "background, black ink line art, simple icons, arrows, containers, and 2-3 accent colors. "
    "Prioritize fast comprehension over decoration. Use short labels only: max 6 words per label, "
    "max 2-3 major text blocks, no paragraph-sized text, no tiny captions, no realistic photos, "
    "no logos, no fake source names. If a fact is long, convert it into a short plain-English label. "
    "The slide should feel like an educational explainer a person could understand in 5 seconds."
)


COMMONWEALTH_REVENUE_FACTS_2024_25 = [
    {"text": "People's income tax: $338b in 2024-25 cash receipts", "kind": "revenue_number"},
    {"text": "Company tax: $139b", "kind": "revenue_number"},
    {"text": "GST: $90b", "kind": "revenue_number"},
    {"text": "Fuel, tobacco, alcohol and customs duties: $43b", "kind": "revenue_number"},
    {"text": "Superannuation fund taxes: $26b", "kind": "revenue_number"},
    {"text": "Petroleum Resource Rent Tax: $1.4b", "kind": "revenue_number"},
]

COMMONWEALTH_SPENDING_FACTS_2025_26 = [
    {"text": "Total Commonwealth expenses: $785.7b in 2025-26", "kind": "spending_number"},
    {"text": "Social security and welfare: $291b, 37% of expenses", "kind": "spending_number"},
    {"text": "Health: $125b, 15.9%", "kind": "spending_number"},
    {"text": "Education: $54b, 6.9%", "kind": "spending_number"},
    {"text": "Defence: $51b, 6.6%", "kind": "spending_number"},
    {"text": "Other purposes: $150b, 19.1%", "kind": "spending_number"},
    {"text": "All other functions: about $83b, 10.6%", "kind": "spending_number"},
]

COMMONWEALTH_SPENDING_TREND_FACTS = [
    {"text": "2006-07 total expenses: $219.4b; 2025-26 total expenses: $785.7b", "kind": "spending_trend"},
    {"text": "Welfare changed from $92.1b, 42.0% in 2006-07 to $291.0b, 37.0% in 2025-26", "kind": "spending_trend"},
    {"text": "Health changed from $39.9b, 18.2% in 2006-07 to $124.8b, 15.9% in 2025-26", "kind": "spending_trend"},
    {"text": "Education changed from $16.9b, 7.7% in 2006-07 to $54.0b, 6.9% in 2025-26", "kind": "spending_trend"},
    {"text": "Defence changed from $16.9b, 7.7% in 2006-07 to $51.5b, 6.6% in 2025-26", "kind": "spending_trend"},
    {"text": "Other purposes changed from $12.3b, 5.6% in 2006-07 to $149.7b, 19.1% in 2025-26", "kind": "spending_trend"},
]

COMMONWEALTH_EXTRA_MONEY_FACTS = [
    {"text": "Total cash receipts rose from $236.7b in 2006-07 to $717.0b in 2024-25: about $480b more coming in each year", "kind": "receipt_growth"},
    {"text": "Individuals and other withholding tax rose from $115.8b to $338.3b: about $222.5b more", "kind": "receipt_growth"},
    {"text": "Company tax rose from $57.1b to $138.8b: about $81.7b more", "kind": "receipt_growth"},
    {"text": "GST receipts rose from $39.6b in 2006-07 to $90.3b in 2024-25: about $50.8b more", "kind": "receipt_growth"},
    {"text": "Superannuation fund taxes rose from $8.2b to $25.7b: about $17.5b more", "kind": "receipt_growth"},
    {"text": "When spending is still higher than receipts, the rest is financed by deficits and debt", "kind": "receipt_growth"},
]

def _commonwealth_tax_per_person_facts() -> list[dict[str, Any]]:
    inputs = normalization_inputs_for_tax_per_resident()
    comparison = build_normalized_comparison(
        inputs["label"],
        start=inputs["start"],
        end=inputs["end"],
        denominators=inputs["denominators"],
    )
    start_pc = round(comparison["start"]["per_capita"] * 1000, -2)
    end_pc = round(comparison["end"]["per_capita"] * 1000, -2)
    pc_change = round(comparison["changes"]["per_capita_change"] * 1000, -2)
    pc_ratio = comparison["changes"]["per_capita_ratio"]
    population_growth = comparison["changes"]["population_growth_rate"]
    source_facts = inputs.get("source_facts") or []
    return [
        {"text": f"Australia's population rose from 21.0m at 30 June 2007 to 27.6m at 30 June 2025: about {population_growth:.0%} more people", "kind": "tax_per_person", "normalization": comparison, "source_facts": source_facts},
        {"text": "Australian Government taxation receipts rose from $217.9b in 2006-07 to $657.8b in 2024-25", "kind": "tax_per_person", "source_facts": source_facts},
        {"text": f"Taxation receipts per resident rose from about ${start_pc:,.0f} to about ${end_pc:,.0f} per person", "kind": "tax_per_person", "source_facts": source_facts},
        {"text": f"That is about ${pc_change:,.0f} more tax collected per resident in nominal dollars, or roughly {pc_ratio:.1f} times the 2006-07 level", "kind": "tax_per_person", "source_facts": source_facts},
        {"text": "This does not prove every person paid that personally; it averages company tax, GST, income tax and other taxes across the population", "kind": "tax_per_person"},
        {"text": "The fair question is: how much is population growth, how much is inflation/wage growth, and how much is heavier tax take?", "kind": "tax_per_person"},
    ]


COMMONWEALTH_TAX_PER_PERSON_FACTS = _commonwealth_tax_per_person_facts()

COMMONWEALTH_TAX_PRESSURE_FACTS = [
    {"text": "Inflation raises prices and nominal wages, so the same tax rates collect more dollars even before real living standards improve", "kind": "tax_pressure"},
    {"text": "Wage growth can push people into higher average tax rates in a progressive income tax system: the Parliamentary Budget Office calls this bracket creep", "kind": "tax_pressure"},
    {"text": "More people and more workers broaden the tax base, but per-person tax can still rise if incomes, prices and profits rise faster than population", "kind": "tax_pressure"},
    {"text": "Government can justify higher revenue by pointing to higher service costs: health, aged care, NDIS, defence, infrastructure and debt interest", "kind": "tax_pressure"},
    {"text": "Budget repair is another reason: governments may let bracket creep raise revenue, then later return some through tax cuts", "kind": "tax_pressure"},
    {"text": "The honest test is percentage burden, not just dollars: tax-to-income, tax-to-GDP, tax-to-budget and real per-person comparisons", "kind": "tax_pressure"},
]

SPENDING_BREAKDOWN_DEEP_DIVES = [
    {
        "slide_type": "spending_breakdown_welfare",
        "title": "Breakdown: welfare",
        "message": "Welfare is the biggest Commonwealth bucket. The useful story is which care and income-support systems drive it, and why they grow.",
        "facts": [
            "2025-26 social security and welfare: $291b, about 37% of Commonwealth expenses",
            "Seniors and age pension support: about $65b among top programs",
            "NDIS: about $52b among top programs",
            "Aged care: about $41b among top programs",
            "Aged-care wage increases total $17.7b, including $2.6b in the 2025-26 Budget",
            "Social safety net increases from recent budgets total $11.5b, including JobSeeker, rent assistance and Parenting Payment changes",
            "Main benefit: income security and care for people who cannot simply earn more",
            "Main pressure: ageing, disability costs, fraud/integrity risk and price growth",
        ],
        "labels": ["Welfare $291b", "Seniors $65b", "NDIS $52b", "Aged care $41b"],
        "benefits": ["income security and care"],
        "negatives": ["ageing and cost growth"],
        "bottom": "Why it grows: ageing + care wages + NDIS packages + indexed payments",
    },
    {
        "slide_type": "spending_breakdown_health",
        "title": "Breakdown: health",
        "message": "Health is not just one bill. The visible investments are GP visits, hospitals, medicines and urgent care — and each gets dearer as demand rises.",
        "facts": [
            "2025-26 health spending: about $125b, about 15.9% of Commonwealth expenses",
            "Health includes Medicare, hospitals, medicines and public-health programs",
            "2025-26 Budget includes $7.9b to expand bulk billing so more people can see a GP for free",
            "2025-26 Budget commits $1.8b to public hospitals and health services",
            "Medicare Urgent Care Clinics have had over 1.3m visits since June 2023",
            "Benefit: people get treatment without paying the full cost alone",
            "Pressure: ageing, new treatments, workforce shortages and waiting lists",
            "Scale check: health is more than twice defence in the 2025-26 reference year",
        ],
        "labels": ["Health $125b", "Bulk billing $7.9b", "Hospitals $1.8b", "Urgent care 1.3m"],
        "benefits": ["GPs, hospitals and medicines"],
        "negatives": ["ageing and workforce pressure"],
        "bottom": "Why it grows: older patients + wages + new treatments + demand",
    },
    {
        "slide_type": "spending_breakdown_education",
        "title": "Breakdown: education",
        "message": "Education spending is smaller than welfare or health, but the investments aim at childcare, schools, TAFE, universities and long-term skills.",
        "facts": [
            "2025-26 education spending: about $54b, about 6.9% of Commonwealth expenses",
            "Education includes schools, universities and training support",
            "2025-26 Budget includes $5b towards a universal early childhood education and care system",
            "Early childhood package includes $3.6b for educator wages and $1b for new places",
            "2025-26 Budget includes $407.5m over four years for Better and Fairer Schools bilateral agreements",
            "Benefit: skills, productivity and opportunity over the long run",
            "Pressure: school funding fights, university costs and whether results improve",
            "Scale check: education is about one fifteenth of total Commonwealth expenses",
        ],
        "labels": ["Education $54b", "Childcare $5b", "Wages $3.6b", "New places $1b"],
        "benefits": ["skills and opportunity"],
        "negatives": ["funding fights"],
        "bottom": "Why it grows: wages + more places + school deals + student demand",
    },
    {
        "slide_type": "spending_breakdown_defence",
        "title": "Breakdown: defence",
        "message": "Defence is not just a generic bucket. The useful story is what Australia is buying: submarines, frigates, missiles, air defence and land capability.",
        "facts": [
            "2025-26 defence spending: about $51b, about 6.6% of Commonwealth expenses",
            "Defence planned expenditure in the 2025-26 PBS is $57.4b: workforce $17.2b, acquisition $18.8b and sustainment $18.8b",
            "2025-26 Top 30 projects include nuclear-powered submarines about $3.3b including other capability inputs",
            "2025-26 Top 30 projects include Hunter class frigates about $1.9b",
            "2025-26 Top 30 projects include Apache attack helicopters about $1.1b",
            "2025-26 Top 30 projects include maritime guided weapons about $781m and Aegis air-defence upgrades about $796m",
            "Reason: the strategy is deterrence — make Australia harder to threaten, especially at sea and from long range",
            "Pressure: large defence projects can run late, over budget or become outdated",
        ],
        "labels": ["Defence $51b", "Subs $3.3b", "Frigates $1.9b", "Missiles $1.6b"],
        "benefits": ["deterrence in the region"],
        "negatives": ["big-project overruns"],
        "bottom": "Why it grows: new equipment + sustainment + workforce costs",
    },
    {
        "slide_type": "spending_breakdown_other",
        "title": "Breakdown: other big bills",
        "message": "The confusing part is 'other'. It includes money passed to states, debt interest, infrastructure and many smaller public services.",
        "facts": [
            "2025-26 other purposes: about $150b, about 19.1% of Commonwealth expenses",
            "All other functions add about $83b, about 10.6% of expenses",
            "GST payments to states are about $101b among top programs",
            "Debt management is about $28.4b in 2025-26",
            "Housing infrastructure incentives include up to $4.5b committed for states and territories",
            "Benefit: state services, infrastructure, administration and interest payments keep government running",
            "Pressure: debt interest buys no new service; it is the cost of past deficits",
        ],
        "labels": ["Other $233b", "States $101b", "Interest $28b", "Housing $4.5b"],
        "benefits": ["state services and infrastructure"],
        "negatives": ["interest buys no new service"],
        "bottom": "Why it grows: GST pool + interest rates + infrastructure commitments",
    },
]

GOVERNMENT_SPENDING_PERIODS = [
    {
        "slide_type": "spending_period_howard_1996_2007",
        "title": "Howard/Costello: 1996-2007",
        "message": "Apples-to-apples: how long they governed, what the budget spent near the end, what people got, and the debt position.",
        "layout": "Use the same government-period template as every card: top band = years and party; left = total spend; middle = four identical buckets; right = benefits; bottom = debt/surplus marker.",
        "facts": [
            "Government period: Coalition, about 11 years from March 1996 to December 2007",
            "Reference year 2006-07: total expenses were $219.4b",
            "Main buckets: welfare $92.1b; health $39.9b; education $16.9b; defence $16.9b",
            "Benefits shown: core services funded, tax cuts/surplus era, Future Fund, low net debt",
            "Debt marker: net debt was negative $24b in 2006-07 and negative $40b in 2007-08",
        ],
        "labels": ["Coalition", "11 years", "$219b spend", "Welfare $92b", "Health $40b", "Debt below zero"],
    },
    {
        "slide_type": "spending_period_rudd_2007_2010",
        "title": "Rudd: 2007-2010",
        "message": "Same template: the big change was the GFC response — emergency spending to protect jobs and demand.",
        "layout": "Same government-period template. Highlight GFC shock icon, stimulus box, household support, school building, and debt line starting to rise.",
        "facts": [
            "Government period: Labor, about 2 years 9 months from December 2007 to June 2010",
            "GFC: 2008-09 deficit was $27.0b as revenue fell and payments jumped",
            "Spending focus: stimulus payments, school infrastructure, insulation/energy programs, early NBN investment",
            "Benefits shown: jobs cushion, household support, construction activity during the global crisis",
            "Debt marker: net debt moved from below zero to positive after the GFC response",
        ],
        "labels": ["Labor", "2.8 years", "GFC", "Stimulus", "Jobs cushion", "Debt turns up"],
    },
    {
        "slide_type": "spending_period_gillard_2010_2013",
        "title": "Gillard: 2010-2013",
        "message": "Same template: disability, schools, health and carbon-policy compensation became major story points.",
        "layout": "Same government-period template. Use identical bucket positions; show NDIS launch, schools, health, carbon compensation, debt marker.",
        "facts": [
            "Government period: Labor, about 3 years from June 2010 to September 2013",
            "Net debt reached $153b by 2011-12 after the GFC period",
            "Spending focus: NDIS foundations, school funding reforms, health agreements, clean-energy household compensation",
            "Benefits shown: disability insurance architecture, education reform, health funding, household compensation",
            "Debt marker: deficits continued after the first GFC shock",
        ],
        "labels": ["Labor", "3 years", "NDIS begins", "Schools", "Health", "Debt $153b"],
    },
    {
        "slide_type": "spending_period_abbott_2013_2015",
        "title": "Abbott/Hockey: 2013-2015",
        "message": "Same template: attempted budget repair, but the debt path still rose and many cuts were politically blocked.",
        "layout": "Same government-period template. Show repair attempt, blocked cuts, health/education debate, defence/security, debt marker.",
        "facts": [
            "Government period: Coalition, about 2 years from September 2013 to September 2015",
            "2013-14 deficit was $48.5b and net debt reached $210b",
            "Spending focus: budget repair attempts, welfare/health/education restraint debates, border/security and defence",
            "Benefits shown: attempted deficit control and security/border priorities",
            "Debt marker: debt kept rising despite repair rhetoric",
        ],
        "labels": ["Coalition", "2 years", "Repair attempt", "Cuts blocked", "Security", "Debt $210b"],
    },
    {
        "slide_type": "spending_period_turnbull_2015_2018",
        "title": "Turnbull/Morrison: 2015-2018",
        "message": "Same template: NDIS and health kept growing, infrastructure and company-tax debates continued, and debt rose.",
        "layout": "Same government-period template. Same buckets; show NDIS ramp, health, infrastructure, schools, debt marker.",
        "facts": [
            "Government period: Coalition, about 3 years from September 2015 to August 2018",
            "Spending focus: NDIS ramp-up, Medicare/health, infrastructure, schools, defence capability",
            "Benefits shown: disability supports expanded, infrastructure pipeline, core services funded",
            "Debt marker: net debt continued climbing toward the pre-COVID $374b level",
            "Continuity point: the structural budget gap persisted before COVID",
        ],
        "labels": ["Coalition", "3 years", "NDIS ramp", "Health", "Infrastructure", "Debt rises"],
    },
    {
        "slide_type": "spending_period_morrison_pre_covid_2018_2020",
        "title": "Morrison/Frydenberg: 2018-2020 pre-COVID",
        "message": "Same template: before COVID, the budget was close to repair, but debt was already much higher than in 2007.",
        "layout": "Same government-period template. Show near-balance marker, tax cuts, drought/bushfire support, services, debt marker.",
        "facts": [
            "Government period before COVID shock: Coalition, about 1.5 years from August 2018 to early 2020",
            "Net debt was $374b by 2018-19 before COVID",
            "Spending focus: tax cuts, drought and bushfire support, health, aged care, defence and NDIS",
            "Benefits shown: household tax relief, disaster support, core services",
            "Debt marker: much higher debt existed before the pandemic shock",
        ],
        "labels": ["Morrison/Frydenberg", "1.5 years", "Tax cuts", "Disasters", "Services", "Debt $374b"],
    },
    {
        "slide_type": "spending_period_morrison_covid_2020_2022",
        "title": "Morrison/Frydenberg: 2020-2022 COVID",
        "message": "Same template: the pandemic created the largest spending shock — support now, debt later.",
        "layout": "Same government-period template. Use crisis badge but keep identical bucket positions; JobKeeper, health response, business cashflow, debt jump.",
        "facts": [
            "Government period during COVID shock: Coalition, about 2 years from early 2020 to May 2022",
            "COVID: 2019-20 and 2020-21 deficits totalled about $219b",
            "Spending focus: JobKeeper, business cashflow support, health response, vaccines and household payments",
            "Benefits shown: income support, business survival, health response during lockdowns",
            "Debt marker: the largest single debt step-up in the story",
        ],
        "labels": ["Morrison/Frydenberg", "2 years", "COVID", "JobKeeper", "Health response", "Debt jump"],
    },
    {
        "slide_type": "spending_period_albanese_2022_2026",
        "title": "Albanese/Chalmers: 2022-2026",
        "message": "Same template: surpluses helped, but the big bills are still welfare, health, NDIS, aged care, states and interest.",
        "layout": "Same government-period template. Show current total spend, top programs, surplus badges, debt-interest marker, and inherited debt context.",
        "facts": [
            "Government period so far: Labor, about 4 years from May 2022 to the 2025-26 Budget year",
            "2025-26 total expenses are estimated at $785.7b",
            "Top programs include states GST support $101b, seniors $65b, NDIS $52b, aged care $41b",
            "Benefits shown: aged care, disability, Medicare/health, cost-of-living and state services",
            "Debt marker: debt management itself is a top program at $28.4b in 2025-26",
        ],
        "labels": ["Labor", "4 years", "$786b spend", "NDIS $52b", "Aged care $41b", "Interest $28b"],
    },
]


GOVERNMENT_SPENDING_DEEP_DIVES = [
    {
        "parent": "spending_period_gillard_2010_2013",
        "slide_type": "spending_detail_gillard_ndis",
        "title": "Gillard deeper: NDIS",
        "message": "Go one level deeper: what was the benefit, what went wrong, and how big is the problem compared with the whole budget?",
        "facts": [
            "Spend item: NDIS foundations and disability insurance architecture",
            "Benefit: life-changing support and more independence for people with disability",
            "Negative: fraud, price inflation, provider quality and cost growth concerns",
            "Scale check: a $5b fraud claim is about 0.5% of $1t debt, but about 10% of a $52b NDIS year",
        ],
        "labels": ["NDIS", "Benefit", "Fraud risk", "$5b vs $1t", "Scale check"],
    },
    {
        "parent": "spending_period_gillard_2010_2013",
        "slide_type": "spending_detail_gillard_carbon",
        "title": "Gillard deeper: carbon package",
        "message": "The same deeper format: household compensation and clean-energy shift on one side, political backlash and costs on the other.",
        "facts": [
            "Spend item: carbon price household compensation and clean-energy support",
            "Benefit: lower-emissions incentives, renewable transition signal, household support",
            "Negative: price scare campaign, business uncertainty, policy repeal risk",
            "Scale check: policy costs should be compared with long-run climate and energy-system benefits",
        ],
        "labels": ["Carbon package", "Renewables", "Compensation", "Backlash", "Repeal risk"],
    },
    {
        "parent": "spending_period_morrison_covid_2020_2022",
        "slide_type": "spending_detail_morrison_jobkeeper",
        "title": "Morrison deeper: JobKeeper",
        "message": "Emergency spending bought real benefits, but also created waste and fairness questions.",
        "facts": [
            "Spend item: JobKeeper and emergency business support",
            "Benefit: kept workers attached to employers and helped businesses survive lockdowns",
            "Negative: overpayments, firms that did not need support, and debt step-up",
            "Scale check: COVID deficits totalled about $219b across 2019-20 and 2020-21",
        ],
        "labels": ["JobKeeper", "Jobs kept", "Overpayment", "$219b deficits", "Debt jump"],
    },
    {
        "parent": "spending_period_albanese_2022_2026",
        "slide_type": "spending_detail_albanese_ndis_aged",
        "title": "Albanese deeper: NDIS and aged care",
        "message": "Current spending has visible human benefits, but cost growth and program integrity decide whether it stays sustainable.",
        "facts": [
            "Spend item: NDIS $52b and aged care $41b among top 2025-26 programs",
            "Benefit: disability support, aged care, workforce and family relief",
            "Negative: cost growth, fraud risk, workforce shortages and service quality problems",
            "Scale check: these programs are huge, but debt interest alone is about $28.4b in 2025-26",
        ],
        "labels": ["NDIS $52b", "Aged care $41b", "Benefits", "Fraud/cost risk", "Interest $28b"],
    },
]

GOVERNMENT_PERIOD_FINANCIALS = {
    "spending_period_howard_1996_2007": {
        "reference_year": "2006-07",
        "total_spend": "$219.4b",
        "welfare": "$92.1b",
        "health": "$39.9b",
        "education": "$16.9b",
        "defence": "$16.9b",
        "debt_start": "-$24b",
        "debt_end": "-$40b",
        "debt_change": "improved $16b",
        "debt_marker": "Debt below zero: -$24b → -$40b",
    },
    "spending_period_rudd_2007_2010": {
        "reference_year": "2009-10",
        "total_spend": "$339.2b",
        "welfare": "$109.2b",
        "health": "$51.4b",
        "education": "$34.9b",
        "defence": "$20.2b",
        "debt_start": "-$40b",
        "debt_end": "$42.3b",
        "debt_change": "+$82b",
        "debt_marker": "Debt turned up: -$40b → $42.3b",
    },
    "spending_period_gillard_2010_2013": {
        "reference_year": "2012-13",
        "total_spend": "$382.6b",
        "welfare": "$131.9b",
        "health": "$61.3b",
        "education": "$28.5b",
        "defence": "$21.1b",
        "debt_start": "$42.3b",
        "debt_end": "$153.0b",
        "debt_change": "+$111b",
        "debt_marker": "Debt rose: $42.3b → $153.0b",
    },
    "spending_period_abbott_2013_2015": {
        "reference_year": "2014-15",
        "total_spend": "$417.9b",
        "welfare": "$147.8b",
        "health": "$65.7b",
        "education": "$31.1b",
        "defence": "$23.8b",
        "debt_start": "$210b",
        "debt_end": "$238.7b",
        "debt_change": "+$29b",
        "debt_marker": "Debt rose: $210b → $238.7b",
    },
    "spending_period_turnbull_2015_2018": {
        "reference_year": "2017-18",
        "total_spend": "$460.3b",
        "welfare": "$157.7b",
        "health": "$76.0b",
        "education": "$33.5b",
        "defence": "$29.3b",
        "debt_start": "$238.7b",
        "debt_end": "$342.0b",
        "debt_change": "+$103b",
        "debt_marker": "Debt rose: $238.7b → $342.0b",
    },
    "spending_period_morrison_pre_covid_2018_2020": {
        "reference_year": "2018-19",
        "total_spend": "$484.7b",
        "welfare": "$170.0b",
        "health": "$80.2b",
        "education": "$34.5b",
        "defence": "$30.8b",
        "debt_start": "$342.0b",
        "debt_end": "$373.6b",
        "debt_change": "+$31.6b",
        "debt_marker": "Debt rose: $342.0b → $373.6b",
    },
    "spending_period_morrison_covid_2020_2022": {
        "reference_year": "2021-22",
        "total_spend": "$623.1b",
        "welfare": "$221.4b",
        "health": "$106.2b",
        "education": "$43.2b",
        "defence": "$38.2b",
        "debt_start": "$373.6b",
        "debt_end": "$515.6b",
        "debt_change": "+$142b",
        "debt_marker": "Debt rose: $373.6b → $515.6b",
    },
    "spending_period_albanese_2022_2026": {
        "reference_year": "2025-26 est.",
        "total_spend": "$785.7b",
        "welfare": "$291b",
        "health": "$125b",
        "education": "$54b",
        "defence": "$51b",
        "debt_start": "$515.6b",
        "debt_end": "$620b est.",
        "debt_change": "+$104b est.",
        "debt_marker": "Net debt: $515.6b → $620b est.",
    },
}


POLITICAL_BACKLASH_FACTS = [
    {"text": "Mining tax fight: industry campaign helped turn a tax design argument into a leadership crisis", "kind": "backlash_example"},
    {"text": "Gas tax fight: industry warnings focus on investment, jobs, energy security, and export buyers", "kind": "backlash_example"},
    {"text": "Voter risk: simple scare messages can beat complex tax explanations", "kind": "backlash_example"},
]

DEBT_CHAPTER_FACTS = {
    "starting_point": [
        {"text": "2006-07: net debt was negative $24b, meaning financial assets exceeded debt", "kind": "debt_context"},
        {"text": "2007-08: net debt fell to negative $40b and the cash surplus was $19.8b", "kind": "debt_context"},
        {"text": "Howard government, Treasurer Peter Costello: late mining-boom surpluses", "kind": "debt_context"},
    ],
    "government_periods": [
        {"text": "Howard/Costello to 2007: net debt moved below zero", "kind": "debt_period"},
        {"text": "Rudd/Gillard: GFC deficits; net debt reached $153b by 2011-12", "kind": "debt_period"},
        {"text": "Abbott/Turnbull/Morrison before COVID: net debt rose to $374b by 2018-19", "kind": "debt_period"},
        {"text": "Morrison/Frydenberg during COVID: deficits of $85b then $134b", "kind": "debt_period"},
        {"text": "Albanese/Chalmers: surpluses in 2022-23 and 2023-24, but high inherited debt remains", "kind": "debt_period"},
    ],
    "shocks": [
        {"text": "GFC: 2008-09 deficit was $27.0b as revenue fell and payments jumped", "kind": "debt_driver"},
        {"text": "2013-14: deficit was $48.5b and net debt reached $210b", "kind": "debt_driver"},
        {"text": "COVID: 2019-20 and 2020-21 deficits totalled about $219b", "kind": "debt_driver"},
        {"text": "Higher rates: interest paid on government securities estimated at $27.9b in 2025-26", "kind": "debt_driver"},
    ],
    "spending_pressure": [
        {"text": "2025-26 spending: welfare $291b, health $125b, education $54b, defence $51b", "kind": "debt_spending"},
        {"text": "Top programs include states GST support $101b, seniors $65b, NDIS $52b, aged care $41b", "kind": "debt_spending"},
        {"text": "Debt management itself is a top program at $28.4b in 2025-26", "kind": "debt_spending"},
    ],
    "why_not_paid_down": [
        {"text": "The key debt test is not whether revenue rises; it is whether revenue is bigger than spending and interest after every year’s promises", "kind": "debt_repair"},
        {"text": "2025-26 expenses are estimated at $785.7b, while 2024-25 total receipts were about $717.0b: the annual budget is still very tight", "kind": "debt_repair"},
        {"text": "Large fixed programs keep absorbing revenue: welfare $291b, health $125b, states GST support $101b, NDIS $52b and aged care $41b", "kind": "debt_repair"},
        {"text": "Debt interest itself is now a major bill: debt management is about $28.4b in 2025-26", "kind": "debt_repair"},
        {"text": "Surpluses in 2022-23 and 2023-24 helped, but they were not large enough to erase the accumulated debt stock", "kind": "debt_repair"},
        {"text": "Politically, paying debt down means running sustained surpluses: higher taxes, lower services, slower benefit growth, or selling assets", "kind": "debt_repair"},
    ],
    "fault": [
        {"text": "2008-12: global shock plus stimulus explain much of the first jump", "kind": "debt_fault"},
        {"text": "2013-19: deficits continued even before COVID", "kind": "debt_fault"},
        {"text": "2020-21: COVID caused the largest single jump", "kind": "debt_fault"},
        {"text": "2022-24: surpluses helped, but did not erase accumulated debt", "kind": "debt_fault"},
        {"text": "Blame map: shocks, spending promises, tax choices, ageing, and weak repair politics", "kind": "debt_fault"},
    ],
    "unwind": [
        {"text": "2025-26 estimate: net debt $620b; securities on issue just over $1.0t", "kind": "debt_unwind"},
        {"text": "Repair options: grow faster, spend less, tax more, accept inflation, or mix them", "kind": "debt_unwind"},
        {"text": "Gas tax enters as one possible revenue source, not the whole debt solution", "kind": "debt_unwind"},
    ],
}


@dataclass
class SlideSpec:
    slide_type: str
    title: str
    message: str
    visual_layout: str
    facts: list[dict[str, Any]]
    labels: list[str]
    image_prompt: str
    slide_id: str = ""
    sequence_index: int | None = None
    chapter: str = ""
    depth: int = 0
    parent: str = ""
    parent_slide_id: str = ""
    parent_slide_index: int | None = None
    depends_on: list[str] | None = None
    template_id: str = ""
    render_contract: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "slide_id": self.slide_id,
            "sequence_index": self.sequence_index,
            "slide_type": self.slide_type,
            "title": self.title,
            "message": self.message,
            "visual_layout": self.visual_layout,
            "facts": self.facts,
            "labels": self.labels,
            "image_prompt": self.image_prompt,
            "chapter": self.chapter,
            "depth": self.depth,
            "parent": self.parent,
            "parent_slide_id": self.parent_slide_id,
            "parent_slide_index": self.parent_slide_index,
            "depends_on": self.depends_on or [],
            "template_id": self.template_id,
            "render_contract": self.render_contract or {},
        }


TIMELINE_META: dict[str, tuple[int, str, str]] = {
    "overview": (0, "Opening", ""),
    "tax_revenue_numbers": (0, "Money context", "overview"),
    "spending_numbers": (1, "Money context", "tax_revenue_numbers"),
    "spending_timeline": (2, "Money context", "spending_numbers"),
    "extra_money_sources": (2, "Money context", "spending_timeline"),
    "tax_per_person": (3, "Money context", "extra_money_sources"),
    "tax_pressure_reasons": (3, "Money context", "tax_per_person"),
    "spending_context": (2, "Money context", "spending_numbers"),
    "politics_context": (0, "Political risk", "overview"),
    "politics_backlash_examples": (1, "Political risk", "politics_context"),
    "decision_fork": (0, "Policy choices", "overview"),
    "supporters_case": (0, "Case for", "decision_fork"),
    "supporters_examples": (1, "Case for", "supporters_case"),
    "country_success_cases": (2, "Case for", "supporters_examples"),
    "opponents_case": (0, "Case against", "decision_fork"),
    "opponents_examples": (1, "Case against", "opponents_case"),
    "country_backfire_cases": (2, "Case against", "opponents_examples"),
    "campaign_influence": (1, "Campaigns", "politics_context"),
    "debt_chapter_intro": (0, "Debt chapter", "overview"),
    "debt_starting_point": (1, "Debt chapter", "debt_chapter_intro"),
    "debt_who_in_power": (1, "Debt chapter", "debt_chapter_intro"),
    "debt_big_shocks": (1, "Debt chapter", "debt_chapter_intro"),
    "debt_where_money_went": (1, "Debt chapter", "debt_chapter_intro"),
    "debt_why_not_paid_down": (2, "Debt chapter", "debt_where_money_went"),
    "debt_fault_map": (2, "Debt chapter", "debt_why_not_paid_down"),
    "debt_unwind_options": (2, "Debt chapter", "debt_fault_map"),
    "debt_power_timeline": (1, "Debt chapter", "debt_chapter_intro"),
    "evidence_check": (0, "Evidence check", "overview"),
    "precedent_timeline": (1, "Evidence check", "evidence_check"),
    "stakeholder_map": (0, "Who is affected", "overview"),
    "confidence_map": (1, "Who is affected", "stakeholder_map"),
    "recommendation": (0, "Conclusion", "overview"),
}


def plan_infographics(
    seed_state: dict[str, Any] | None,
    tree: dict[str, Any] | None,
    *,
    format: str | None = "landscape",
) -> dict[str, Any]:
    """Return a deterministic, render-ready infographic sequence.

    The sequence is deliberately more like a story timeline than a dense
    decision tree: one simple idea per slide, with deeper subchapter slides
    when the researched tree contains story-depth nodes.
    """

    seed_state = seed_state or {}
    tree = tree or {}
    output_format = _normalise_format(format)
    topic = seed_state.get("topic") or tree.get("question") or "Policy explainer"
    branches = _top_level_branches(tree)
    nodes = _flatten(tree) if tree else []

    slides: list[SlideSpec] = [
        _overview_slide(topic, tree, output_format),
        _tax_numbers_slide(topic, output_format),
        _spending_numbers_slide(topic, output_format),
        *_spending_breakdown_slides(topic, output_format),
        _spending_timeline_slide(topic, output_format),
        _extra_money_sources_slide(topic, output_format),
        _tax_per_person_slide(topic, output_format),
        _tax_pressure_reasons_slide(topic, output_format),
        *_spending_period_slides(topic, output_format),
        _spending_context_slide(topic, nodes, output_format),
        _politics_context_slide(topic, nodes, output_format),
        _politics_backlash_examples_slide(topic, nodes, output_format),
    ]

    if branches:
        slides.append(_decision_fork_slide(topic, branches, output_format))

    slides.extend([
        _supporters_case_slide(topic, branches, nodes, output_format),
    ])
    _append_if(slides, _supporters_examples_slide(topic, nodes, output_format))
    slides.append(_opponents_case_slide(topic, branches, nodes, output_format))
    _append_if(slides, _opponents_examples_slide(topic, nodes, output_format))

    _append_if(slides, _country_success_slide(topic, nodes, output_format))
    _append_if(slides, _country_backfire_slide(topic, nodes, output_format))
    _append_if(slides, _campaign_influence_slide(topic, nodes, output_format))

    if _has_debt_story(nodes):
        slides.extend(_debt_subchapter_slides(topic, nodes, output_format))
    else:
        _append_if(slides, _debt_timeline_slide(topic, nodes, output_format))

    slides.extend([
        _evidence_check_slide(topic, nodes, output_format),
    ])
    _append_if(slides, _precedents_slide(topic, nodes, output_format))
    slides.extend([
        _stakeholder_slide(topic, seed_state, nodes, output_format),
        _confidence_slide(topic, nodes, output_format),
        _recommendation_slide(topic, tree, branches, output_format),
    ])

    _annotate_timeline_metadata(slides)
    sequence = [slide.to_dict() for slide in slides]
    return {
        "schema_version": "infographic-plan/v1",
        "topic": topic,
        "output_format": output_format,
        "aspect_ratio": "9:16" if output_format == "tiktok" else "16:9",
        "style_preset": STYLE_PRESET,
        "style_preprompt": STYLE_PREPROMPT,
        "slide_count": len(sequence),
        "sequence": sequence,
    }


def plan_generic_education_infographics(
    topic: str,
    claims: list[str | dict[str, Any]] | None = None,
    *,
    format: str | None = "landscape",
    audience_level: str = "general_public",
) -> dict[str, Any]:
    """Create renderable infographic slides from the generic education planner.

    This is the bridge from universal claim-question methodology to the existing
    slide renderer. It intentionally uses placeholder fact requirements until a
    research/fact-ledger layer fills real sourced facts.
    """

    output_format = _normalise_format(format)
    education_plan = plan_education_sequence(
        topic=topic,
        claims=claims or [],
        audience_level=audience_level,
    )
    slides = [_slide_from_lesson_beat(beat, output_format) for beat in education_plan["lesson_beats"]]
    _annotate_timeline_metadata(slides)
    sequence = [slide.to_dict() for slide in slides]
    return {
        "schema_version": "infographic-plan/v1",
        "planner": "generic_education",
        "education_plan": education_plan,
        "topic": topic or "Untitled topic",
        "output_format": output_format,
        "aspect_ratio": "9:16" if output_format == "tiktok" else "16:9",
        "style_preset": STYLE_PRESET,
        "style_preprompt": STYLE_PREPROMPT,
        "slide_count": len(sequence),
        "sequence": sequence,
    }


def plan_gas_tax_public_explainer(
    seed_state: dict[str, Any] | None = None,
    tree: dict[str, Any] | None = None,
    *,
    format: str | None = "tiktok",
) -> dict[str, Any]:
    """Return the concise 15-slide public explainer for the gas-tax pilot.

    The full ``plan_infographics`` output is a master curriculum. This plan is
    the publication-oriented cut: it keeps the gas/resource-tax question central,
    uses the budget/debt slides only as supporting context, and adds the missing
    public-education beats (surface claim, resource rent, design questions, and
    what each side omits).
    """

    seed_state = seed_state or {}
    tree = tree or {}
    output_format = _normalise_format(format or "tiktok")
    topic = seed_state.get("topic") or tree.get("question") or "Australian gas tax debate"

    slides: list[SlideSpec] = [
        _public_slide(
            "public_hook",
            "Should gas companies pay more tax?",
            "This is not just a tax fight. It is a story about public resources, private profits, government services, and investment risk.",
            "Opening path: gas field icon to company profits, public budget, and a balanced trade-off scale.",
            [
                "Gas is a public resource extracted by private firms",
                "The debate is about fair public return versus investment certainty",
                "Budget and debt context explain what extra revenue can and cannot solve",
            ],
            ["Public resource", "Private profit", "Public budget", "Trade-off"],
            output_format,
            chapter="Opening",
            source_slide_ids=["opening.overview"],
        ),
        _public_slide(
            "public_surface_claim",
            "Two slogans hide the real question",
            "The public hears two simple claims: gas companies should pay more, and new taxes will scare investment. Both claims need context.",
            "Two megaphones facing each other: one says 'fair share', the other says 'investment risk'. Put a question mark between them.",
            [
                "Supporters frame the issue as a fair-share question",
                "Opponents frame the issue as an investment-risk question",
                "The useful test is what is true, missing, contested and design-dependent",
            ],
            ["Fair share", "Investment risk", "What is missing?"],
            output_format,
            chapter="Opening",
            source_slide_ids=[],
        ),
        _public_slide(
            "public_resource_rent",
            "What is being taxed?",
            "A resource-rent tax targets extra profits from publicly owned natural resources, not ordinary wages or normal business costs.",
            "Layer diagram: public underground gas resource, extraction company, normal costs and returns, then a highlighted 'resource rent' slice.",
            [
                "Resource rent means returns above normal costs and normal profit",
                "The public-owner argument is that citizens should capture a fair share of that rent",
                "The design problem is separating rent from ordinary investment returns",
            ],
            ["Public gas", "Normal costs", "Normal profit", "Resource rent"],
            output_format,
            chapter="Gas tax basics",
            source_slide_ids=[],
        ),
        _tax_numbers_slide(topic, output_format),
        _spending_numbers_slide(topic, output_format),
        _tax_per_person_slide(topic, output_format),
        _extra_money_sources_slide(topic, output_format),
        _tax_pressure_reasons_slide(topic, output_format),
        _debt_why_not_paid_down_slide(topic, output_format),
        _public_slide(
            "public_gas_tax_fit",
            "Where does a gas tax fit?",
            "A gas tax is one possible revenue source. It may help, but it is not the whole budget or debt solution.",
            "Decision fork for debt repair: grow, spend less, tax more, mix. Put gas tax as one branch under 'tax more'.",
            [
                "Debt repair choices are grow faster, spend less, tax more, or mix them",
                "Gas tax enters as one revenue branch, not the whole solution",
                "Revenue use matters: services, cost-of-living relief, debt repair or future fund",
            ],
            ["Grow", "Spend less", "Tax more", "Gas tax branch", "Use matters"],
            output_format,
            chapter="Budget context",
            source_slide_ids=["debt.unwind_options"],
        ),
        _public_slide(
            "public_case_for",
            "The strongest case for taxing more",
            "Supporters argue Australia should capture more value from public resources and use it for services, debt repair, or future generations.",
            "Public resource flows to a fair-return box, then branches to citizens, services, debt repair and future fund.",
            [
                "The pro-tax case is that public resources should deliver a fair public return",
                "Supporters often point to resource-rent principles and international examples",
                "The public benefit should be stated clearly, not left vague",
            ],
            ["Fair return", "Services", "Debt repair", "Future fund"],
            output_format,
            chapter="Case for",
            source_slide_ids=["claims.supporters_case", "precedents.success_cases"],
        ),
        _public_slide(
            "public_case_against",
            "The strongest case against taxing more",
            "Opponents warn that sudden or poorly designed taxes can reduce investment, supply, jobs, or trust in policy rules.",
            "Tax shock arrow leading to investor concern, then supply, jobs and policy-trust warning icons.",
            [
                "The anti-tax case is strongest when focused on design risk, not blanket opposition",
                "Bad timing or unstable rules can raise investment and supply concerns",
                "The question is which risks are evidenced, exaggerated or manageable",
            ],
            ["Design risk", "Investment concern", "Supply warning", "Policy trust"],
            output_format,
            chapter="Case against",
            source_slide_ids=["claims.opponents_case", "precedents.backfire_cases"],
        ),
        _public_slide(
            "public_design_questions",
            "The debate is really design",
            "Once you get past slogans, the practical questions are rate, base, deductions, transition, price triggers, revenue use and transparency.",
            "Checklist card titled 'Good tax design?' with seven ticks and a small warning icon for rushed design.",
            [
                "Important design choices include rate, tax base, deductions and transition rules",
                "A price trigger can target windfalls more narrowly than a broad permanent change",
                "Public trust improves when revenue use and evidence are transparent",
            ],
            ["Rate", "Base", "Deductions", "Transition", "Revenue use"],
            output_format,
            chapter="Policy design",
            source_slide_ids=[],
        ),
        _public_slide(
            "public_omissions",
            "What each side leaves out",
            "Industry often downplays public ownership and resource rent. Tax advocates can understate investment risk and design complexity.",
            "Two-column card: 'industry may omit' and 'tax advocates may omit', with a fair-explanation bridge below.",
            [
                "Industry messages may omit public ownership and rent-capture arguments",
                "Tax-advocacy messages may omit investment, supply and design risks",
                "A fair explanation should steelman both sides before concluding",
            ],
            ["Industry omits", "Advocates omit", "Steelman both"],
            output_format,
            chapter="How to think",
            source_slide_ids=["evidence.confidence_map", "stakeholders.map"],
        ),
        _public_slide(
            "public_honest_answer",
            "The honest answer",
            "More tax can be justified if it is evidence-based, stable, targeted at rents, transparent, and paired with a clear public benefit.",
            "Balanced bridge between 'fair public return' and 'investment certainty', with a middle path labelled 'good design'.",
            [
                "The honest question is not simply tax or no tax",
                "Better question: what design gives Australians fair return without avoidable harm?",
                "Clear public benefit and stable rules are central to legitimacy",
            ],
            ["Fair return", "Good design", "Investment certainty"],
            output_format,
            chapter="Conclusion",
            source_slide_ids=["conclusion.recommendation"],
        ),
    ]

    _annotate_public_explainer_metadata(slides)
    sequence = [slide.to_dict() for slide in slides]
    return {
        "schema_version": "infographic-plan/v1",
        "planner": "gas_tax_public_explainer",
        "topic": topic,
        "output_format": output_format,
        "aspect_ratio": "9:16" if output_format == "tiktok" else "16:9",
        "style_preset": STYLE_PRESET,
        "style_preprompt": STYLE_PREPROMPT,
        "slide_count": len(sequence),
        "sequence": sequence,
    }


def _public_slide(
    slide_type: str,
    title: str,
    message: str,
    visual_layout: str,
    fact_texts: list[str],
    labels: list[str],
    output_format: str,
    *,
    chapter: str,
    source_slide_ids: list[str],
) -> SlideSpec:
    facts = [_fact(text, f"{slide_type}_fact") for text in fact_texts]
    slide = _slide(
        slide_type,
        title,
        message,
        visual_layout,
        facts,
        labels,
        output_format,
        chapter=chapter,
        slide_id=f"public.{slide_type.removeprefix('public_').replace('_', '.')}",
        depends_on=source_slide_ids,
    )
    slide.render_contract = {
        "source_slide_ids": source_slide_ids,
        "publication_role": "public_explainer",
    }
    return slide


def _annotate_public_explainer_metadata(slides: list[SlideSpec]) -> None:
    for index, slide in enumerate(slides):
        slide.slide_id = slide.slide_id or _stable_slide_id(slide.slide_type)
        slide.sequence_index = index
        if index > 0:
            parent = slides[index - 1]
            slide.parent = parent.slide_type
            slide.parent_slide_id = parent.slide_id
            slide.parent_slide_index = index - 1
        slide.depends_on = _slide_dependencies(slide)


def _slide_from_lesson_beat(beat: dict[str, Any], output_format: str) -> SlideSpec:
    fact_requirements = beat.get("facts_needed") or []
    facts = [
        _fact(f"Research needed: {requirement}", beat.get("question_id") or "education_requirement")
        for requirement in fact_requirements[:MAX_PROMPT_FACTS]
    ]
    return _slide(
        beat.get("slide_type") or beat.get("question_id") or "education_beat",
        beat.get("title") or "Education beat",
        beat.get("teaching_goal") or beat.get("voiceover") or "Explain this claim clearly and fairly.",
        beat.get("visual_metaphor") or "Simple educational card with one clear idea, one diagram, and minimal text.",
        facts,
        [_short_label(item, 34) for item in fact_requirements[:5]],
        output_format,
        chapter="Education method",
        depth=0,
        slide_id=beat.get("slide_id") or "education.beat",
        depends_on=[beat.get("question_id", "education")],
    )


def _append_if(slides: list[SlideSpec], slide: SlideSpec | None) -> None:
    if slide is not None:
        slides.append(slide)


def _annotate_timeline_metadata(slides: list[SlideSpec]) -> None:
    """Ensure every slide carries backend-native timeline hierarchy metadata."""

    index_by_type = {slide.slide_type: index for index, slide in enumerate(slides)}
    id_by_type = {slide.slide_type: _stable_slide_id(slide.slide_type) for slide in slides}
    for slide in slides:
        slide.slide_id = slide.slide_id or _stable_slide_id(slide.slide_type)
        slide.sequence_index = index_by_type.get(slide.slide_type)
        default_depth, default_chapter, default_parent = TIMELINE_META.get(
            slide.slide_type,
            (slide.depth, slide.chapter or "Story beat", slide.parent),
        )
        if not slide.chapter:
            slide.chapter = default_chapter
        if slide.depth == 0 and default_depth:
            slide.depth = default_depth
        if not slide.parent:
            slide.parent = default_parent
        if slide.parent:
            slide.parent_slide_index = index_by_type.get(slide.parent)
            slide.parent_slide_id = id_by_type.get(slide.parent, _stable_slide_id(slide.parent))
        slide.depends_on = _slide_dependencies(slide)


def _stable_slide_id(slide_type: str) -> str:
    """Return a deterministic content identity independent of sequence index."""

    explicit = {
        "overview": "opening.overview",
        "tax_revenue_numbers": "money.tax_revenue_numbers",
        "spending_numbers": "money.spending_numbers",
        "spending_timeline": "money.spending_timeline",
        "extra_money_sources": "money.extra_sources",
        "tax_per_person": "money.tax_per_person",
        "tax_pressure_reasons": "money.tax_pressure_reasons",
        "spending_context": "money.spending_context",
        "politics_context": "politics.context",
        "politics_backlash_examples": "politics.backlash_examples",
        "decision_fork": "policy.decision_fork",
        "supporters_case": "claims.supporters_case",
        "supporters_examples": "claims.supporters_examples",
        "opponents_case": "claims.opponents_case",
        "opponents_examples": "claims.opponents_examples",
        "country_success_cases": "precedents.success_cases",
        "country_backfire_cases": "precedents.backfire_cases",
        "campaign_influence": "politics.campaign_influence",
        "debt_chapter_intro": "debt.chapter_intro",
        "debt_starting_point": "debt.starting_point",
        "debt_who_in_power": "debt.who_in_power",
        "debt_big_shocks": "debt.big_shocks",
        "debt_where_money_went": "debt.where_money_went",
        "debt_why_not_paid_down": "debt.why_not_paid_down",
        "debt_fault_map": "debt.fault_map",
        "debt_unwind_options": "debt.unwind_options",
        "debt_power_timeline": "debt.power_timeline",
        "evidence_check": "evidence.claim_check",
        "precedent_timeline": "evidence.precedent_timeline",
        "stakeholder_map": "stakeholders.map",
        "confidence_map": "evidence.confidence_map",
        "recommendation": "conclusion.recommendation",
    }
    if slide_type in explicit:
        return explicit[slide_type]
    return slide_type.replace("_", ".")


def _slide_dependencies(slide: SlideSpec) -> list[str]:
    deps: list[str] = []
    if slide.parent_slide_id:
        deps.append(slide.parent_slide_id)
    for fact in slide.facts or []:
        fact_id = fact.get("fact_id") or fact.get("node_id") or fact.get("kind")
        if fact_id:
            deps.append(f"fact:{fact_id}")
    return list(dict.fromkeys(deps))


def _overview_slide(topic: str, tree: dict[str, Any], output_format: str) -> SlideSpec:
    facts = [_node_fact(tree, kind="overview")] if tree else [_fact(topic, "overview")]
    return _slide(
        "overview",
        "Should gas companies pay more tax?",
        "This story is about public resources, private profits, government services, and the risks of changing tax rules.",
        "Opening title card: gas field icon, public money icon, and a simple path into the story timeline.",
        facts,
        ["Public resource", "Private profit", "Public services", "Tax rules"],
        output_format,
    )


def _has_debt_story(nodes: list[dict[str, Any]]) -> bool:
    return any(_matches(n, ("debt", "2006", "who was in power", "trillion", "budget deficit")) for n in nodes)


def _tax_numbers_slide(topic: str, output_format: str) -> SlideSpec:
    return _slide(
        "tax_revenue_numbers",
        "What tax does Canberra actually collect?",
        "Most Commonwealth tax money comes from workers and companies. Gas-specific PRRT is tiny beside income tax.",
        "Accurate simple pie chart using the supplied dollar amounts. Make income tax and company tax visibly largest; PRRT is a tiny sliver.",
        COMMONWEALTH_REVENUE_FACTS_2024_25,
        ["Income tax $338b", "Company tax $139b", "GST $90b", "Duties $43b", "PRRT $1.4b"],
        output_format,
    )


def _spending_numbers_slide(topic: str, output_format: str) -> SlideSpec:
    return _slide(
        "spending_numbers",
        "Where does the money go?",
        "Use dollars first. The reference point is the cash: about $786b total, with welfare, health, education, defence, and other purposes the big buckets.",
        "Accurate simple pie chart using the supplied dollar amounts. Put dollar labels bigger than percentages; no unlabeled slices.",
        COMMONWEALTH_SPENDING_FACTS_2025_26,
        ["Total $786b", "Welfare $291b", "Health $125b", "Education $54b", "Defence $51b", "Other $233b"],
        output_format,
    )


def _spending_timeline_slide(topic: str, output_format: str) -> SlideSpec:
    return _slide(
        "spending_timeline",
        "How has spending changed since 2006?",
        "The cash total is much larger now. The mix also changed: other purposes grew sharply, while welfare remains the biggest bucket.",
        "Two-column comparison timeline: 2006-07 on the left, 2025-26 on the right. Show dollars and percentages for the main buckets.",
        COMMONWEALTH_SPENDING_TREND_FACTS,
        ["2006: $219b", "2025: $786b", "Welfare 42%→37%", "Other purposes 5.6%→19.1%"],
        output_format,
    )


def _extra_money_sources_slide(topic: str, output_format: str) -> SlideSpec:
    return _slide(
        "extra_money_sources",
        "Where does the extra money come from?",
        "The bigger spending total is mostly paid for by a much bigger tax base: workers, companies, GST and super funds. Any remaining gap becomes deficit and debt.",
        "Flow diagram: left side shows 2006 receipts; right side shows 2024-25 receipts. Use thick arrows for workers' income tax, company tax, GST, super, and a small debt-gap arrow.",
        COMMONWEALTH_EXTRA_MONEY_FACTS,
        ["Receipts +$480b", "Workers +$222b", "Companies +$82b", "GST +$51b", "Gap = debt"],
        output_format,
    )


def _tax_per_person_slide(topic: str, output_format: str) -> SlideSpec:
    return _slide(
        "tax_per_person",
        "Is each person being taxed more?",
        "Yes in nominal per-person terms: tax collected per resident more than doubled. But this average includes company tax, GST and other taxes, not just personal income tax.",
        "Two-step comparison: population bar grows modestly from 21.0m to 27.6m, while tax-per-resident bar grows much faster from $10.4k to $23.8k. Add a caution label: average across all taxes.",
        COMMONWEALTH_TAX_PER_PERSON_FACTS,
        ["People +31%", "Tax/person $10.4k→$23.8k", "2.3× nominal", "Not just income tax"],
        output_format,
    )


def _tax_pressure_reasons_slide(topic: str, output_format: str) -> SlideSpec:
    return _slide(
        "tax_pressure_reasons",
        "Why can tax per person rise?",
        "Governments can collect more per person without announcing a new tax: inflation, wage growth, bracket creep, bigger profits, service costs and debt repair all push revenue up.",
        "Simple cause-and-effect board. Centre: 'more tax per person'. Around it: inflation, wages, bracket creep, more services, debt interest, budget repair. Add a final check: compare percentages, not just dollars.",
        COMMONWEALTH_TAX_PRESSURE_FACTS,
        ["Inflation", "Wages", "Bracket creep", "Service costs", "Debt repair", "Check % burden"],
        output_format,
    )


def _spending_breakdown_slides(topic: str, output_format: str) -> list[SlideSpec]:
    slides = []
    for detail in SPENDING_BREAKDOWN_DEEP_DIVES:
        slides.append(_slide(
            detail["slide_type"],
            detail["title"],
            detail["message"],
            "Use the strict spending-category drilldown template: left = big category dollars; middle grid = four meaningful sub-items; right = benefits and pressures; bottom = plain scale check. No vague labels.",
            [_fact(text, "spending_category_breakdown") for text in detail["facts"]],
            detail["labels"],
            output_format,
            chapter="Where the money goes",
            depth=2,
            parent="spending_numbers",
            template_id="SPENDING_BREAKDOWN",
            render_contract=_spending_breakdown_contract(detail),
        ))
    return slides


def _spending_period_slides(topic: str, output_format: str) -> list[SlideSpec]:
    slides = []
    for period in GOVERNMENT_SPENDING_PERIODS:
        slide_type = period["slide_type"]
        slides.append(_slide(
            slide_type,
            period["title"],
            period["message"],
            period["layout"],
            [_fact(text, "government_spending_period") for text in period["facts"]],
            period["labels"],
            output_format,
            chapter="By government",
            depth=2,
            parent="spending_timeline",
            template_id="GOV_SPEND_CARD",
            render_contract=_government_spending_contract(period),
        ))
        for detail in [d for d in GOVERNMENT_SPENDING_DEEP_DIVES if d["parent"] == slide_type]:
            slides.append(_slide(
                detail["slide_type"],
                detail["title"],
                detail["message"],
                "Use the strict deeper spending-item template. Keep this visually indented from the parent government card, but preserve the same benefits/negatives/scale-check layout across all deeper cards.",
                [_fact(text, "government_spending_detail") for text in detail["facts"]],
                detail["labels"],
                output_format,
                chapter="By government",
                depth=3,
                parent=slide_type,
                template_id="GOV_SPEND_DETAIL",
                render_contract=_government_detail_contract(detail),
            ))
    return slides


def _government_spending_contract(period: dict[str, Any]) -> dict[str, Any]:
    labels = period.get("labels") or []
    facts = period.get("facts") or []
    financials = GOVERNMENT_PERIOD_FINANCIALS.get(period.get("slide_type", ""), {})
    return {
        "template": "government_spending_card",
        "reference_image": "slide-05.png",
        "strict_layout": True,
        "map_to_reference_blocks": {
            "top_title": period.get("title"),
            "top_party_flag": labels[0] if len(labels) > 0 else "",
            "top_calendar": financials.get("reference_year") or _years_from_title_text(period.get("title", "")),
            "top_duration": labels[1] if len(labels) > 1 else "",
            "left_total_spend": financials.get("total_spend") or _extract_total_spend(facts) or "TBD",
            "middle_bucket_1": {"label": "Welfare", "value": financials.get("welfare") or _extract_bucket_value(facts, "welfare") or "focus"},
            "middle_bucket_2": {"label": "Health", "value": financials.get("health") or _extract_bucket_value(facts, "health") or "focus"},
            "middle_bucket_3": {"label": "Education", "value": financials.get("education") or _extract_bucket_value(facts, "education") or "focus"},
            "middle_bucket_4": {"label": "Defence", "value": financials.get("defence") or _extract_bucket_value(facts, "defence") or "focus"},
            "right_benefits": _split_contract_items(_extract_prefixed(facts, ("Benefits shown:", "Benefit story:"))),
            "right_negatives": _split_contract_items(_infer_period_negative(period.get("title", ""), facts)),
            "bottom_debt_marker": financials.get("debt_marker") or _extract_prefixed(facts, ("Debt marker:",)) or _extract_debt_marker(facts),
            "debt_change": financials.get("debt_change", ""),
        },
        "must_include": ["top_title", "top_party_flag", "top_duration", "left_total_spend", "right_benefits", "right_negatives", "bottom_debt_marker"],
        "forbid_inventing_numbers": True,
    }


def _government_detail_contract(detail: dict[str, Any]) -> dict[str, Any]:
    facts = detail.get("facts") or []
    labels = detail.get("labels") or []
    spend_item = _extract_prefixed(facts, ("Spend item:",))
    benefit = _extract_prefixed(facts, ("Benefit:",))
    negative = _extract_prefixed(facts, ("Negative:",))
    scale = _extract_prefixed(facts, ("Scale check:",))
    return {
        "template": "government_spending_detail_card",
        "reference_image": "slide-05.png",
        "strict_layout": True,
        "parent": detail.get("parent"),
        "map_to_reference_blocks": {
            "top_title": detail.get("title"),
            "top_party_flag": _parent_party_label(detail.get("parent", "")),
            "top_calendar": "deeper dive",
            "top_duration": "1 issue",
            "left_total_spend": labels[0] if labels else spend_item,
            "middle_bucket_1": {"label": "What it pays for", "value": _short_contract_value(spend_item, 34)},
            "middle_bucket_2": {"label": "Who benefits", "value": _short_contract_value(benefit, 34)},
            "middle_bucket_3": {"label": "What can go wrong", "value": _short_contract_value(negative, 34)},
            "middle_bucket_4": {"label": "Debt context", "value": _short_contract_value(scale, 34)},
            "right_benefits": _split_contract_items(benefit),
            "right_negatives": _split_contract_items(negative),
            "bottom_debt_marker": scale,
        },
        "must_include": ["top_title", "left_total_spend", "right_benefits", "right_negatives", "bottom_debt_marker"],
        "forbid_inventing_numbers": True,
    }


def _spending_breakdown_contract(detail: dict[str, Any]) -> dict[str, Any]:
    labels = detail.get("labels") or []
    facts = detail.get("facts") or []
    category_total = labels[0] if labels else ""
    category_label, category_value = _split_label_value(category_total)
    return {
        "template": "spending_category_breakdown_card",
        "reference_image": "slide-05.png",
        "strict_layout": True,
        "parent": "spending_numbers",
        "map_to_reference_blocks": {
            "top_title": detail.get("title"),
            "top_party_flag": "2025-26 Budget",
            "top_calendar": "category",
            "top_duration": "drilldown",
            "left_category_label": category_label,
            "left_category_value": category_value,
            "left_total_spend": category_total,
            "middle_bucket_1": _label_value_from_label(labels, 1, "Sub-item 1"),
            "middle_bucket_2": _label_value_from_label(labels, 2, "Sub-item 2"),
            "middle_bucket_3": _label_value_from_label(labels, 3, "Sub-item 3"),
            "middle_bucket_4": {"label": "Why it grows", "value": _growth_driver_from_bottom(detail.get("bottom", ""))},
            "right_benefits": detail.get("benefits") or _split_contract_items(_extract_prefixed(facts, ("Benefit:", "Main benefit:"))),
            "right_negatives": detail.get("negatives") or _split_contract_items(_extract_prefixed(facts, ("Pressure:", "Main pressure:"))),
            "bottom_debt_marker": detail.get("bottom") or _extract_prefixed(facts, ("Scale check:",)),
        },
        "must_include": ["top_title", "left_total_spend", "middle_bucket_1", "middle_bucket_2", "middle_bucket_3", "middle_bucket_4", "right_benefits", "right_negatives", "bottom_debt_marker"],
        "forbid_inventing_numbers": True,
    }


def _spending_context_slide(topic: str, nodes: list[dict[str, Any]], output_format: str) -> SlideSpec:
    picked = _pick_nodes(nodes, ("welfare", "health", "defence", "services", "spend", "spending"), limit=3)
    facts = [_node_fact(n, kind="spending_context") for n in picked] or [_fact("Government spending includes welfare, health, aged care, defence, education, and public services.", "spending_context")]
    return _slide(
        "spending_context",
        "What does government spend money on?",
        "A tax debate makes more sense when people can see the bills government is trying to pay.",
        "Simple pie or bucket diagram showing welfare, health, schools, defence, infrastructure, and debt interest.",
        facts,
        ["Welfare", "Health", "Schools", "Defence", "Infrastructure", "Debt interest"],
        output_format,
    )


def _politics_context_slide(topic: str, nodes: list[dict[str, Any]], output_format: str) -> SlideSpec:
    picked = _pick_nodes(nodes, ("albanese", "government avoid", "political risk", "resource-state", "electorates", "why might"), limit=3)
    facts = [_node_fact(n, kind="politics_context") for n in picked] or [_fact("Governments may avoid a popular-sounding tax if it risks jobs claims, investor warnings, or backlash in key seats.", "politics_context")]
    return _slide(
        "politics_context",
        "Why might politicians avoid it?",
        "Even if a tax sounds simple, leaders weigh voter backlash, industry campaigns, investment warnings, and budget politics.",
        "Plain-English political-risk map with voters, industry, investors, and government in separate corners.",
        facts,
        ["Voters", "Gas industry", "Investors", "Key seats", "Budget politics"],
        output_format,
    )


def _politics_backlash_examples_slide(topic: str, nodes: list[dict[str, Any]], output_format: str) -> SlideSpec:
    picked = _pick_nodes(nodes, ("rspt", "mrrt", "campaign", "backlash", "political risk", "industry"), limit=3)
    facts = [_node_fact(n, kind="backlash_example") for n in picked] or POLITICAL_BACKLASH_FACTS
    return _slide(
        "politics_backlash_examples",
        "What backlash can look like",
        "Politicians do not just fear the tax. They fear the campaign that follows it.",
        "Three simple example cards: mining tax campaign, gas industry warnings, voter scare message. Use arrows from policy to backlash.",
        facts[:3],
        ["Industry ads", "Jobs warning", "Investment threat", "Voter scare"],
        output_format,
    )


def _supporters_case_slide(topic: str, branches: list[dict[str, Any]], nodes: list[dict[str, Any]], output_format: str) -> SlideSpec:
    support_nodes = [n for n in nodes if _matches(n, ("support", "public", "revenue", "fair", "extra profit", "relief", "tax more"))]
    facts = [_node_fact(n, kind="support_case") for n in _sorted_by_salience(support_nodes)[:3]] or [
        _fact("Supporters say public resources should return more public money when profits jump.", "support_case"),
    ]
    return _slide(
        "supporters_case",
        "The case for taxing more",
        "Supporters make one simple claim: if gas profits jump, the public should share more of the upside.",
        "One-sided explainer card: public resource → extra profit → public services. Keep it simple and persuasive but factual.",
        facts,
        ["Public resource", "Extra profit", "Public services", "Fair return"],
        output_format,
    )


def _supporters_examples_slide(topic: str, nodes: list[dict[str, Any]], output_format: str) -> SlideSpec | None:
    picked = _pick_nodes(nodes, ("worked", "norway", "public value", "sovereign wealth", "success"), limit=3)
    if not picked:
        return None
    return _slide(
        "supporters_examples",
        "Supporters point to examples",
        "The stronger pro-tax story uses examples where resource wealth was turned into visible public benefit.",
        "Two or three small example cards. Show what worked, not a crowded world map.",
        [_node_fact(n, kind="support_example") for n in picked],
        [_country_or_short_label(n) for n in picked],
        output_format,
    )


def _opponents_case_slide(topic: str, branches: list[dict[str, Any]], nodes: list[dict[str, Any]], output_format: str) -> SlideSpec:
    oppose_nodes = [n for n in nodes if _matches(n, ("oppose", "risk", "investment", "jobs", "energy security", "scare investors", "backlash"))]
    facts = [_node_fact(n, kind="oppose_case") for n in _sorted_by_salience(oppose_nodes)[:3]] or [
        _fact("Opponents say rule changes can scare investment and threaten supply, jobs, or trade relationships.", "oppose_case"),
    ]
    return _slide(
        "opponents_case",
        "The case against taxing more",
        "Opponents make one simple warning: sudden tax changes can scare investment and create wider risks.",
        "One-sided explainer card: new tax → investor concern → jobs/supply/trade warnings. Make it clear this is the opponent argument.",
        facts,
        ["Rule change", "Investment risk", "Jobs claim", "Supply warning"],
        output_format,
    )


def _opponents_examples_slide(topic: str, nodes: list[dict[str, Any]], output_format: str) -> SlideSpec | None:
    picked = _pick_nodes(nodes, ("backfire", "rspt", "mrrt", "failed", "campaign", "political disaster"), limit=3)
    if not picked:
        return None
    return _slide(
        "opponents_examples",
        "Opponents point to backlash",
        "The stronger anti-tax story uses examples where reform became a costly political fight.",
        "Two or three caution cards: campaign, confusion, retreat. Keep each example to one short lesson.",
        [_node_fact(n, kind="oppose_example") for n in picked],
        [_country_or_short_label(n) for n in picked],
        output_format,
    )

def _decision_fork_slide(topic: str, branches: list[dict[str, Any]], output_format: str) -> SlideSpec:
    picked = branches[:4]
    facts = [_node_fact(b) for b in picked]
    labels = [_short_label(b.get("question", "Option"), 34) for b in picked]
    return _slide(
        "decision_fork",
        "The main choices on the table",
        f"The issue breaks into {len(picked)} main viewpoints or choices that can be compared side by side.",
        "Horizontal fork diagram from the central question into option cards, one card per viewpoint.",
        facts,
        labels,
        output_format,
    )


def _pros_cons_slide(topic: str, branches: list[dict[str, Any]], output_format: str) -> SlideSpec:
    facts = []
    labels = []
    for branch in branches[:3]:
        labels.append(_short_label(branch.get("question", "Viewpoint"), 28))
        pro, con = _branch_pro_con(branch)
        if pro:
            facts.append(_node_fact(pro, kind="argument_for"))
        if con:
            facts.append(_node_fact(con, kind="argument_against"))
    return _slide(
        "viewpoint_compare",
        "Arguments supporters and opponents will use",
        "Each option has a public-facing case for it and a risk story opponents will push back with.",
        "Three-column comparison grid. Each column has a green 'case for' row and amber/red 'risk' row.",
        facts[:MAX_PROMPT_FACTS],
        labels,
        output_format,
    )


def _evidence_check_slide(topic: str, nodes: list[dict[str, Any]], output_format: str) -> SlideSpec:
    claim_nodes = [n for n in nodes if _looks_like_claim_check(n)] or _sorted_by_salience(nodes)
    picked = claim_nodes[:4]
    facts = [_node_fact(n, kind="claim_check") for n in picked]
    labels = [_short_label(n.get("question", "Claim"), 36) for n in picked]
    return _slide(
        "evidence_check",
        "Which claims need checking?",
        "The strongest infographic should separate asserted claims from what the evidence actually supports.",
        "Claim-check board with cards labelled 'claim', 'what evidence says', and confidence markers.",
        facts,
        labels,
        output_format,
    )


def _precedents_slide(topic: str, nodes: list[dict[str, Any]], output_format: str) -> SlideSpec | None:
    precedent_nodes = [n for n in nodes if _matches(n, ("norway", "uk", "spain", "italy", "rspt", "mrrt", "precedent", "elsewhere"))]
    if not precedent_nodes:
        return None
    precedent_nodes = sorted(precedent_nodes, key=_precedent_rank)
    picked = precedent_nodes[:5]
    facts = [_node_fact(n, kind="precedent") for n in picked]
    labels = [_country_or_short_label(n) for n in picked]
    return _slide(
        "precedent_timeline",
        "What happened elsewhere?",
        "Comparable resource and windfall tax cases show both revenue-capture successes and political/investment backlash risks.",
        "World-map or timeline strip with one small card per precedent and a short lesson under each.",
        facts,
        labels,
        output_format,
    )


def _country_success_slide(topic: str, nodes: list[dict[str, Any]], output_format: str) -> SlideSpec | None:
    picked = _pick_nodes(nodes, ("where did it work", "worked", "norway", "success", "higher resource", "windfall taxes"), limit=4)
    if not picked:
        return None
    facts = [_node_fact(n, kind="worked_elsewhere") for n in picked]
    labels = [_country_or_short_label(n) for n in picked]
    return _slide(
        "country_success_cases",
        "Where has this kind of tax worked?",
        "Good examples usually combine clear rules, stable design, and a visible public benefit from the money raised.",
        "Simple world-map lesson board: green example cards connected to the design features that made them work.",
        facts,
        labels,
        output_format,
    )


def _country_backfire_slide(topic: str, nodes: list[dict[str, Any]], output_format: str) -> SlideSpec | None:
    picked = _pick_nodes(nodes, ("backfire", "backlash", "rspt", "mrrt", "failed", "investment", "political fight"), limit=4)
    if not picked:
        return None
    facts = [_node_fact(n, kind="backfire_case") for n in picked]
    labels = [_country_or_short_label(n) for n in picked]
    return _slide(
        "country_backfire_cases",
        "Where did it go wrong?",
        "Failures are often about design, timing, public trust, and campaigns — not just the word tax.",
        "Timeline of warning signs: rushed design, industry campaign, voter confusion, investor fear, policy retreat.",
        facts,
        labels,
        output_format,
    )


def _campaign_influence_slide(topic: str, nodes: list[dict[str, Any]], output_format: str) -> SlideSpec | None:
    picked = _pick_nodes(nodes, ("campaign", "misinformation", "misleading", "gas dollars", "industry", "advertising", "lobby", "public debate"), limit=4)
    if not picked:
        return None
    facts = [_node_fact(n, kind="campaign_influence") for n in picked]
    labels = ["Paid campaigns", "Lobbying", "Simple slogans", "Confusing claims"]
    return _slide(
        "campaign_influence",
        "Who shapes the story people hear?",
        "Big tax fights can become message wars. The system should show who is paying, what they claim, and what evidence says.",
        "Megaphone diagram: money flows into ads and talking points; fact-check cards separate evidence from spin.",
        facts,
        labels,
        output_format,
    )



def _debt_subchapter_slides(topic: str, nodes: list[dict[str, Any]], output_format: str) -> list[SlideSpec]:
    # This is a deterministic scaffold. Research/synthesis can later replace the
    # facts with exact yearly debt and spending figures.
    return [
        _slide(
            "debt_chapter_intro",
            "How did debt get here?",
            "Before blaming one party, show the timeline: who governed, what shocks hit, and what spending grew.",
            "Simple chapter title card: rising debt line from 2006 to today with question marks for cause, blame, and repair.",
            [_fact("Debt story = governments + shocks + spending + revenue choices", "debt_chapter")],
            ["Who governed?", "What happened?", "Where spent?", "How unwind?"],
            output_format,
        ),
        _slide(
            "debt_starting_point",
            "Start: low debt before the shocks",
            "The story starts with low debt and mining-boom revenue before the GFC changed the budget picture.",
            "Timeline start card: 2006 marker, Howard/Costello label, low-debt baseline, mining boom icon.",
            DEBT_CHAPTER_FACTS["starting_point"],
            ["2006", "Howard", "Costello", "Low debt"],
            output_format,
        ),
        _slide(
            "debt_who_in_power",
            "Who was in power as debt rose?",
            "Show the debt line under each government so viewers see timing before blame.",
            "Horizontal timeline with coloured government bands and exact milestone labels: -$40b, $153b, $374b, $592b, $620b estimate.",
            DEBT_CHAPTER_FACTS["government_periods"],
            ["Howard", "Rudd/Gillard", "Coalition", "Albanese"],
            output_format,
        ),
        _slide(
            "debt_big_shocks",
            "What shocks pushed debt up?",
            "The biggest jumps came from crises and then the rising cost of carrying the debt.",
            "Three large shock cards on the timeline: GFC deficit $27b, COVID deficits $219b, interest paid $27.9b. Use simple icons.",
            DEBT_CHAPTER_FACTS["shocks"],
            ["GFC", "COVID", "Higher rates"],
            output_format,
        ),
        _slide(
            "debt_where_money_went",
            "Where did the money go?",
            "To explain debt honestly, show where the big money goes now: welfare, health, NDIS, aged care, states, and interest.",
            "Stacked spending buckets with dollar labels flowing into a debt line. Keep labels large and simple.",
            DEBT_CHAPTER_FACTS["spending_pressure"],
            ["Welfare", "Health", "NDIS", "Aged care", "Defence", "Interest"],
            output_format,
        ),
        _slide(
            "debt_why_not_paid_down",
            "Why is debt not being paid down?",
            "More tax money does not automatically reduce debt. If spending promises, service costs and interest absorb the revenue, debt only falls when governments run sustained surpluses.",
            "Leaky bucket visual: extra tax flows in at the top, then big holes drain to welfare, health, NDIS, states, defence, interest and new promises. Only leftover surplus flows to debt repayment.",
            DEBT_CHAPTER_FACTS["why_not_paid_down"],
            ["More revenue", "Big services", "Interest bill", "New promises", "Surplus pays debt"],
            output_format,
        ),
        _slide(
            "debt_fault_map",
            "So who is really at fault?",
            "The honest answer separates shocks from choices: GFC, COVID, ongoing deficits, spending promises, and weak repair politics.",
            "Accountability map with four time blocks and a separate shock bucket. Avoid party logos; focus on evidence.",
            DEBT_CHAPTER_FACTS["fault"],
            ["Choices", "Shocks", "Ageing", "Tax design", "Politics"],
            output_format,
        ),
        _slide(
            "debt_unwind_options",
            "How do you unwind debt?",
            "The repair choices are simple but hard: grow faster, spend less, tax more, or mix them.",
            "Decision fork for debt repair with the $620b net debt and $1.0t securities labels. Connect gas tax as one revenue branch.",
            DEBT_CHAPTER_FACTS["unwind"],
            ["Grow", "Spend less", "Tax more", "Inflation", "Mix"],
            output_format,
        ),
    ]


def _debt_why_not_paid_down_slide(topic: str, output_format: str) -> SlideSpec:
    return _slide(
        "debt_why_not_paid_down",
        "Why is debt not being paid down?",
        "More tax money does not automatically reduce debt. If spending promises, service costs and interest absorb the revenue, debt only falls when governments run sustained surpluses.",
        "Leaky bucket visual: extra tax flows in at the top, then big holes drain to welfare, health, NDIS, states, defence, interest and new promises. Only leftover surplus flows to debt repayment.",
        DEBT_CHAPTER_FACTS["why_not_paid_down"],
        ["More revenue", "Big services", "Interest bill", "New promises", "Surplus pays debt"],
        output_format,
    )


def _debt_timeline_slide(topic: str, nodes: list[dict[str, Any]], output_format: str) -> SlideSpec | None:
    picked = _pick_nodes(nodes, ("debt", "2006", "who was in power", "timeline", "government debt"), limit=3)
    if not picked:
        return None
    facts = [_node_fact(n, kind="debt_timeline") for n in picked]
    return _slide(
        "debt_power_timeline",
        "How did debt get here?",
        "A debt timeline gives context: which governments were in power, what shocks happened, and why new revenue is politically tempting.",
        "Horizontal timeline from 2006 to today with government-change markers, shock icons, and rising debt line.",
        facts,
        ["2006", "GFC", "COVID", "Higher rates", "Today"],
        output_format,
    )


def _stakeholder_slide(topic: str, seed_state: dict[str, Any], nodes: list[dict[str, Any]], output_format: str) -> SlideSpec:
    stakeholders = [s.get("name") for s in seed_state.get("stakeholders", []) if isinstance(s, dict) and s.get("name")]
    if not stakeholders:
        stakeholders = _extract_stakeholders(nodes)
    labels = [_short_label(s, 24) for s in stakeholders[:6]] or ["Government", "Companies", "Households", "Investors"]
    facts = [_fact(f"{label}: interests and risks should be shown separately, not blended into one generic public interest.", "stakeholder") for label in labels[:MAX_PROMPT_FACTS]]
    return _slide(
        "stakeholder_map",
        "Who gains, who pays, who worries?",
        "A useful infographic makes the affected groups visible before arguing for a conclusion.",
        "Hub-and-spoke stakeholder map around the central policy question, with benefit/risk tags on each spoke.",
        facts,
        labels,
        output_format,
    )


def _confidence_slide(topic: str, nodes: list[dict[str, Any]], output_format: str) -> SlideSpec:
    scored = [n for n in nodes if isinstance(n.get("scores"), dict)]
    high = sum(1 for n in scored if n["scores"].get("confidence") == "high")
    medium = sum(1 for n in scored if n["scores"].get("confidence") == "medium")
    low = sum(1 for n in scored if n["scores"].get("confidence") == "low")
    disputed = sum(1 for n in scored if n["scores"].get("contestedness") in {"disputed", "contested"})
    facts = [
        _fact(f"High-confidence points: {high}", "confidence_count"),
        _fact(f"Medium-confidence points: {medium}", "confidence_count"),
        _fact(f"Low-confidence or thin-evidence points: {low}", "confidence_count"),
        _fact(f"Contested or disputed points: {disputed}", "contested_count"),
    ]
    return _slide(
        "confidence_map",
        "What is solid, and what is still contested?",
        "The audience needs to see which parts of the argument are evidence-backed and which remain uncertain.",
        "2x2 matrix: high vs low confidence crossed with settled vs contested, using coloured dot clusters.",
        facts,
        ["High confidence", "Medium", "Low / thin", "Contested"],
        output_format,
    )


def _recommendation_slide(topic: str, tree: dict[str, Any], branches: list[dict[str, Any]], output_format: str) -> SlideSpec:
    fact = _node_fact(tree, kind="synthesis")
    labels = [_short_label(b.get("question", "Option"), 24) for b in branches[:3]] + ["Sensible compromise"]
    return _slide(
        "recommendation",
        "A sensible way to explain the trade-off",
        fact["text"],
        "Decision scale or balanced bridge visual: public revenue on one side, investment certainty on the other, compromise path through the middle.",
        [fact],
        labels,
        output_format,
    )


def _slide(
    slide_type: str,
    title: str,
    message: str,
    visual_layout: str,
    facts: list[dict[str, Any]],
    labels: list[str],
    output_format: str = "landscape",
    *,
    chapter: str = "",
    depth: int = 0,
    parent: str = "",
    slide_id: str = "",
    depends_on: list[str] | None = None,
    template_id: str = "",
    render_contract: dict[str, Any] | None = None,
) -> SlideSpec:
    clean_facts = [f for f in facts if f.get("text")][:MAX_PROMPT_FACTS]
    clean_labels = [_short_label(l, 42) for l in labels if l][:8]
    return SlideSpec(
        slide_type=slide_type,
        title=_clean(title),
        message=_truncate(_plain_language(_clean(message)), 170 if output_format == "tiktok" else 220),
        visual_layout=_clean(visual_layout),
        facts=clean_facts,
        labels=[_plain_language(l) for l in clean_labels],
        image_prompt=_image_prompt(title, message, visual_layout, clean_facts, clean_labels, output_format, template_id=template_id),
        slide_id=slide_id,
        chapter=chapter,
        depth=depth,
        parent=parent,
        depends_on=depends_on or [],
        template_id=template_id,
        render_contract=render_contract,
    )


def _image_prompt(title: str, message: str, visual_layout: str, facts: list[dict[str, Any]], labels: list[str], output_format: str = "landscape", *, template_id: str = "") -> str:
    fact_lines = "\n".join(f"- {_short_prompt_fact(f['text'])}" for f in facts[:MAX_PROMPT_FACTS]) or "- No specific facts supplied. Use only the title and labels."
    label_line = ", ".join(_short_label(_plain_language(label), 28) for label in labels) if labels else "No extra labels"
    format_line = (
        "Format: vertical 9:16 TikTok/Reels/Shorts card. One idea only. Big central drawing. Very few words."
        if output_format == "tiktok" else
        "Format: horizontal 16:9 web/social infographic. One clear idea with simple supporting labels."
    )
    template_line = ""
    if template_id == "GOV_SPEND_CARD":
        template_line = (
            "STRICT TEMPLATE: GOV_SPEND_CARD. Every government-period slide MUST use the same layout and camera angle: "
            "top band with party + years + time in office; left big box 'TOTAL SPEND'; middle 2x2 grid with the same four buckets "
            "(Welfare, Health, Education, Defence/Other); right column split into 'BENEFITS' and 'NEGATIVES'; bottom thin debt/surplus arrow. "
            "Only the numbers and short labels change. Do not change composition, chart type, colors, or icon positions between cards.\n"
            "RENDER_CONTRACT_JSON: {template:'GOV_SPEND_CARD', must_include_title:true, must_include_all_exact_labels:true, "
            "fixed_sections:['TOTAL SPEND','Welfare','Health','Education','Defence/Other','BENEFITS','NEGATIVES','Debt marker'], "
            "forbidden:['changing layout','omitting treasurer name','replacing dollar labels with vague icons']}.\n"
        )
    elif template_id == "GOV_SPEND_DETAIL":
        template_line = (
            "STRICT TEMPLATE: GOV_SPEND_DETAIL. Every deeper spending-item slide MUST use the same layout: top parent-government band; "
            "left 'SPEND ITEM'; middle grid with meaningful labels ('What it pays for', 'Who benefits', 'What can go wrong', 'Debt context'); "
            "right column split into 'BENEFITS' and 'NEGATIVES / RISKS'; bottom 'SCALE CHECK' showing how large the issue is against total spending or $1t debt. "
            "Only numbers and labels change. Keep layout identical across detail cards.\n"
            "RENDER_CONTRACT_JSON: {template:'GOV_SPEND_DETAIL', must_include_title:true, must_include_all_exact_labels:true, "
            "fixed_sections:['SPEND ITEM','What it pays for','Who benefits','What can go wrong','Debt context','BENEFITS','NEGATIVES / RISKS','SCALE CHECK'], "
            "forbidden:['vague labels like scale/context/evidence','omitting scale comparison','turning pros/cons into decoration']}.\n"
        )
    elif template_id == "SPENDING_BREAKDOWN":
        template_line = (
            "STRICT TEMPLATE: SPENDING_BREAKDOWN. Each category drilldown MUST use the same layout: top band says 2025-26 Budget; "
            "left big category total with the category name above the dollar amount; middle 2x2 grid with real sub-items; right column split into 'BENEFITS' and 'PRESSURES'; bottom plain scale check. "
            "No vague labels such as scale/context/evidence. Only render the supplied dollar amounts and labels.\n"
            "RENDER_CONTRACT_JSON: {template:'SPENDING_BREAKDOWN', must_include_all_exact_labels:true, "
            "fixed_sections:['left category name + dollar amount','four sub-items','BENEFITS','PRESSURES','SCALE CHECK'], "
            "forbidden:['vague labels','inventing subcategories','changing layout']}.\n"
        )
    return (
        f"Create one simple educational infographic slide.\n"
        f"{format_line}\n"
        f"{template_line}"
        f"{STYLE_PREPROMPT}\n"
        f"Title text: {_short_label(_plain_language(title), 56 if output_format == 'tiktok' else 72)}\n"
        f"Main message to communicate visually, not as a paragraph: {_truncate(_plain_language(message), 95 if output_format == 'tiktok' else 150)}\n"
        f"Suggested layout: {visual_layout}\n"
        f"Exact short labels to use where useful: {label_line}\n"
        f"Facts to convert into simple visual callouts:\n{fact_lines}\n"
        "Composition rules: make the hierarchy obvious; use arrows to show flow; use icons for people, money, risk, evidence, and trade-offs; "
        "keep all text large; leave generous whitespace; do not create a giant text block; do not invent numbers, sources, logos, or quotes. "
        "For vertical TikTok format, use no more than 14 total words on the image. For number slides, use only the largest 4-5 labels plus percentages or dollar amounts."
    )


def _top_level_branches(tree: dict[str, Any]) -> list[dict[str, Any]]:
    return [c for c in tree.get("children", []) if isinstance(c, dict)]


def _flatten(node: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    def walk(n: dict[str, Any]) -> None:
        out.append(n)
        for child in n.get("children", []) or []:
            if isinstance(child, dict):
                walk(child)
    walk(node)
    return out


def _node_fact(node: dict[str, Any], *, fallback: str = "", kind: str = "node") -> dict[str, Any]:
    scores = node.get("scores") if isinstance(node.get("scores"), dict) else {}
    text = scores.get("stance_summary") or _first_sentence(node.get("summary")) or fallback or node.get("question") or ""
    return _fact(text, kind, node)


def _fact(text: str, kind: str, node: dict[str, Any] | None = None) -> dict[str, Any]:
    item = {
        "text": _truncate(_plain_language(_clean(text)), MAX_FACT_CHARS),
        "kind": kind,
    }
    if node:
        item["node_id"] = node.get("id")
        item["node_type"] = node.get("type")
        scores = node.get("scores") if isinstance(node.get("scores"), dict) else {}
        if scores:
            item["confidence"] = scores.get("confidence")
            item["contestedness"] = scores.get("contestedness")
            item["salience"] = scores.get("salience")
    return item


def _branch_pro_con(branch: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    children = branch.get("children", []) or []
    pro = None
    con = None
    for child in children:
        text = f"{child.get('question', '')} {child.get('summary', '')} {child.get('scores', {}).get('stance_summary', '')}".lower()
        if pro is None and any(w in text for w in ("revenue", "public", "benefit", "fair", "support", "relief", "rent")):
            pro = child
        if con is None and any(w in text for w in ("risk", "deter", "flight", "price", "cost", "credit", "sovereign", "objection")):
            con = child
    return pro or (children[0] if children else branch), con or (children[1] if len(children) > 1 else None)



def _pick_nodes(nodes: list[dict[str, Any]], needles: tuple[str, ...], limit: int) -> list[dict[str, Any]]:
    matches = [n for n in nodes if _matches(n, needles)]
    return _sorted_by_salience(matches)[:limit]

def _sorted_by_salience(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    weight = {"high": 0, "moderate": 1, "niche": 2}
    return sorted(nodes, key=lambda n: weight.get((n.get("scores") or {}).get("salience"), 3))


def _looks_like_claim_check(node: dict[str, Any]) -> bool:
    q = (node.get("question") or "").lower()
    return "claim" in q or "accurate" in q or "evidence" in q or "will" in q


def _matches(node: dict[str, Any], needles: tuple[str, ...]) -> bool:
    haystack = f"{node.get('question', '')} {node.get('summary', '')} {node.get('scores', {}).get('stance_summary', '')}".lower()
    return any(n in haystack for n in needles)


def _extract_stakeholders(nodes: list[dict[str, Any]]) -> list[str]:
    known = ["Government", "Gas companies", "Households", "Manufacturers", "Investors", "Export buyers", "Future taxpayers"]
    text = " ".join((n.get("question") or "") + " " + (n.get("summary") or "") for n in nodes).lower()
    return [k for k in known if k.lower().split()[0] in text]


def _precedent_rank(node: dict[str, Any]) -> tuple[int, int]:
    q = (node.get("question") or "").lower()
    if node.get("type") == "analogy" and any(k in q for k in ("norway", "uk", "united kingdom", "spain", "italy", "rspt", "mrrt")):
        return (0, len(q))
    if any(k in q for k in ("norway", "uk", "united kingdom", "spain", "italy", "rspt", "mrrt")):
        return (1, len(q))
    if node.get("type") == "analogy":
        return (2, len(q))
    return (3, len(q))


def _country_or_short_label(node: dict[str, Any]) -> str:
    text = (node.get("question") or "").lower()
    for label in ("Norway", "UK", "Spain", "Italy", "Australia RSPT/MRRT"):
        if label.lower().split()[0] in text or (label == "UK" and "united kingdom" in text):
            return label
    return _short_label(node.get("question", "Precedent"), 26)


def _years_from_title_text(text: str) -> str:
    import re
    match = re.search(r"\d{4}[–-]\d{4}", text or "")
    return match.group(0) if match else ""


def _extract_total_spend(facts: list[str]) -> str:
    import re
    joined = " ".join(facts)
    patterns = [
        r"total expenses (?:were|are estimated at) \$([0-9.]+b)",
        r"Reference year [^:]+: total expenses were \$([0-9.]+b)",
    ]
    for pattern in patterns:
        match = re.search(pattern, joined, flags=re.I)
        if match:
            return "$" + match.group(1)
    return ""


def _extract_bucket_value(facts: list[str], bucket: str) -> str:
    import re
    joined = " ".join(facts)
    match = re.search(bucket + r"\s+\$?([0-9.]+b)", joined, flags=re.I)
    return "$" + match.group(1) if match else ""


def _extract_prefixed(facts: list[str], prefixes: tuple[str, ...]) -> str:
    for fact in facts:
        for prefix in prefixes:
            if fact.startswith(prefix):
                return fact[len(prefix):].strip()
    return ""


def _extract_debt_marker(facts: list[str]) -> str:
    for fact in facts:
        if "net debt" in fact.lower() or "debt" in fact.lower():
            return fact
    return ""


def _split_contract_items(text: str) -> list[str]:
    if not text:
        return []
    import re
    return [item.strip(" .") for item in re.split(r";|, and | and ", text) if item.strip(" .")][:4]


def _short_contract_value(text: str, max_len: int = 34) -> str:
    return _short_label(_plain_language(text), max_len) if text else ""


def _split_label_value(label: str) -> tuple[str, str]:
    parts = (label or "").rsplit(" ", 1)
    if len(parts) == 2 and any(ch.isdigit() for ch in parts[1]):
        return parts[0], parts[1]
    return label, ""


def _label_value_from_label(labels: list[str], index: int, fallback_label: str) -> dict[str, str]:
    label = labels[index] if len(labels) > index else fallback_label
    label_text, value = _split_label_value(label)
    return {"label": label_text, "value": value}


def _growth_driver_from_bottom(text: str) -> str:
    cleaned = (text or "").replace("Why it grows:", "").strip()
    return _short_label(cleaned, 36)


def _parent_party_label(parent: str) -> str:
    if "gillard" in parent or "rudd" in parent or "albanese" in parent:
        return "Labor"
    if "howard" in parent or "abbott" in parent or "turnbull" in parent or "morrison" in parent:
        return "Coalition"
    return "deeper dive"


def _infer_period_negative(title: str, facts: list[str]) -> str:
    explicit = _extract_prefixed(facts, ("Negative:", "Cost story:"))
    if explicit:
        return explicit
    title = (title or "").lower()
    if "howard" in title:
        return "Future obligations remained; boom revenue made choices easier"
    if "rudd" in title:
        return "Deficits began; some stimulus waste and program failures"
    if "gillard" in title:
        return "Cost growth; backlash; design fights"
    if "abbott" in title:
        return "Cuts blocked; repair politics hurt trust"
    if "turnbull" in title:
        return "Structural gap persisted; debt kept rising"
    if "morrison" in title and "covid" not in title:
        return "Debt already high before the pandemic"
    if "covid" in title:
        return "Overpayments; large permanent debt step-up"
    if "albanese" in title:
        return "Cost growth; fraud risk; high interest bill"
    return "Trade-offs and long-term costs"


def _first_sentence(text: str | None) -> str:
    if not text:
        return ""
    clean = _clean(text.replace("**", ""))
    for sep in (". ", "? ", "! "):
        if sep in clean:
            return clean.split(sep, 1)[0] + sep.strip()
    return clean



def _plain_language(text: str) -> str:
    replacements = {
        "active, partisan debate": "big public argument",
        "partisan debate": "political argument",
        "industry-aligned analysis": "gas industry reports",
        "progressive think tanks": "tax reform groups",
        "crossbench senators": "independent senators",
        "levy": "tax",
        "fiscal": "tax",
        "sovereign risk": "risk that rule changes scare investors",
        "contested": "argued over",
        "disputed": "argued over",
        "salience": "public attention",
        "windfall": "extra profit",
    }
    out = text
    for old, new in replacements.items():
        out = out.replace(old, new).replace(old.title(), new.title())
    return out

def _normalise_format(format: str | None) -> str:
    value = (format or "landscape").strip().lower()
    if value in {"tiktok", "tik-tok", "reels", "shorts", "vertical", "9:16"}:
        return "tiktok"
    return "landscape"


def _short_prompt_fact(text: str) -> str:
    text = _plain_language(_clean(text))
    # Image models handle short, direct callouts better than paragraph facts.
    text = text.replace("Evidence points to ", "")
    text = text.replace("The evidence ", "Evidence ")
    return _truncate(text, 110)


def _short_label(text: str, max_len: int) -> str:
    text = _clean(text)
    text = text.replace("Is this claim accurate:", "Claim:")
    return _truncate(text, max_len)


def _truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    return text[:max_len].rsplit(" ", 1)[0].rstrip(" ,;:") + "…"


def _clean(value: Any) -> str:
    return " ".join(str(value or "").split())
