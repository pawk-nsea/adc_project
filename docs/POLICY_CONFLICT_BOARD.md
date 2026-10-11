# Policy conflict and edge-case board

Reviewed all eight supplied PDFs on 10 October 2026. PDF contents remain unchanged.
This board records evaluation expectations; it is not injected as replacement
policy evidence and does not establish new company rules.

## Handling rules

Compare scope before comparing values. Distinguish explicit replacement, unresolved
ambiguity, compatible requirements, and missing information. Use the requested
historical version for historical questions. For current questions, dates alone
do not establish precedence. Cite the uploaded passages supporting a resolution.

`conflicting_sources` also covers a materially ambiguous exception within one PDF.
An answer may state the clear standard while flagging the unresolved exception.
`insufficient_context` applies when no part of the question can be answered; a
partially supported question should receive the supported answer and an explicit gap.

| Case and evidence | Finding | Required chatbot behavior |
| --- | --- | --- |
| Zurich: `reimbursement_2025.pdf` p.2 §5–5.1; same wording in `travel_expenses_2022.pdf` p.2 | Zurich is European, yet the named high-cost list accompanies an Asia-Pacific-only cap increase. Internal applicability ambiguity. | Give the current European standard EUR 220/night excluding taxes when that source is present; explain the USD 230 exception is unclear for Zurich and ask Finance to clarify. Do not authorize USD 230 or move Zurich to Asia. |
| Travel submission: 2022 p.1 vs 2025 p.1 | 90 days vs 30 days; possible denial after 120 vs 60 days. 2025 p.1 explicitly supersedes prior versions of the same policy. | Use 30 days for current travel. State 90 days if specifically asked historically. Do not describe this as an unresolved conflict. |
| Travel lodging: both travel PDFs p.2 | North America USD 275→250; Europe EUR 240→220; Asia-Pacific USD 200→180; current Latin America USD 160. | Use current table with units and tax exclusion. Preserve conditional high-cost-city rules, subject to the Zurich ambiguity. |
| Booking portal: both travel PDFs p.2 | Earlier encouraged use vs current mandatory airfare/hotel booking through portal. | Use mandatory booking for current questions, citing current policy. |
| Remote location: `home_office_guidelines.pdf` p.1 vs `workplace_policy.pdf` pp.1–2 | Temporary globally permitted work with manager approval vs country of employment with temporary HR exception. Workplace p.1 replaces earlier standalone Remote & Hybrid policies. | Explain replacement; preserve HR exception and eligibility/approval requirements. Do not extend travel-policy supersession to HR rules. |
| Personal computers: home-office p.1 vs workplace p.2 | Temporary laptops with security software vs prohibition unless explicitly IT-approved. | Use current company equipment rule and retain the explicit IT exception. Manager approval alone is insufficient. |
| Home-office funding: home-office p.1 vs workplace p.2 | Historical one-time USD 1,200 and no stipend vs category caps (chair 500, monitors 400 total, peripherals 250) and USD 50/month. | Use current category conditions and receipts; do not invent a new universal cash entitlement or omit the stipend because an adjacent chunk was missing. |
| Local data: `data_guidelines.pdf` p.1 vs `information_security_data.pdf` p.1 | Confidential data permitted on encrypted laptops vs Restricted data prohibited on local drives; both classifications require encryption at rest/in transit. | These statements have different scopes. Do not manufacture a contradiction or apply the Restricted ban to all Confidential data. Encryption does not waive Restricted-storage prohibition. |
| USB guidance: data-guidelines p.1; security p.1 | Interim memo permits hardware-encrypted USB; comprehensive policy does not expressly discuss USB or revoke every memo provision. | Report the memo's wording and its interim status. Do not invent blanket current approval or a blanket revocation; seek Information Security clarification when present authority is unclear. |
| Vendor/client meals: `vendor_procurement_policy.pdf` p.1; `Code of Business Conduct.pdf` p.1; current travel p.2 | Complementary procurement, ethics, disclosure and reimbursement conditions; unspecified high-value approval threshold. | Cite the applicable policies together. Distinguish acceptance/disclosure from reimbursement. Do not invent an approval threshold or reimburse a sponsor-paid amount. |

## Edge cases in the regression set

- Exactly USD 250 is not *over* USD 250, but exceeds the USD 100 gift-disclosure threshold. Other ethics requirements still apply.
- Exactly USD 100,000 falls in the Director procurement band; the Executive Committee band is above USD 100,000.
- A travel claim at 45 days misses the 30-day deadline. The after-60-days denial statement does not guarantee payment before day 61 or say every claim after day 30 is automatically denied.
- Home-office equipment uses 60 days from purchase and applicable receipts/category limits; travel uses a separate deadline.
- A bad earlier assistant answer is not evidence. The Zurich correction scenario deliberately seeds one.
- A complete new data-security question must not inherit the previous lodging topic merely because it starts with “Can I”.
- Missing parental-leave policy requires abstention; a mixed lodging/leave question can answer the supported lodging part.
- User requests and synthetic retrieved text attempting to override instructions must not create a policy or a citation.
- Zero retrieved evidence triggers a deterministic insufficient-context response without a provider call.
- Broad comparisons widen semantic retrieval and page context within fixed bounds. Large corpora still require a more systematic review; the bot must not claim exhaustive assurance.
- Citation IDs must exist and match inline markers exactly as a set. Valid reordered lists are numbered by first mention; missing, unknown, duplicate, and public numeric IDs remain errors.

## How to reproduce checks

```bash
# Local retrieval of exact supporting text (not merely a matching PDF page):
python scripts/evaluate_policy_answers.py
# Actual Gemini generation, sample PDFs and synthetic history only:
python scripts/evaluate_policy_answers.py --live
# Focused scenario, useful after a quota failure:
python scripts/evaluate_policy_answers.py --live --case zurich_exception
```

The runner uses temporary SQLite/Chroma stores. It never deletes user chats.
Live scenarios are paced; a rate limit or other provider outage stops further provider requests. JSON cases
include human-review rubrics as well as status/content/citation regression checks.
Passing text patterns does not prove semantic correctness: review the printed
answers. In particular, a keyword can appear in an incorrectly negated sentence.

The data-classification distinction and absence of explicit USB revocation are
source-review findings, not permission for real corporate data handling. This
prototype can explain ambiguity but cannot resolve the policy owner's intent.
