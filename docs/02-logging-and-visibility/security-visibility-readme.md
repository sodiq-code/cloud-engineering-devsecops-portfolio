# Week 2 – AWS Security Visibility Setup

This week I focused on building basic visibility for a cloud security analyst workflow:

## Components

1. **CloudTrail**
   - Single-region trail for management events
   - Logs stored in private S3 bucket: `afsod-cloudtrail-logs-12345`
   - Verified via Event history that API calls are being recorded

2. **GuardDuty**
   - Enabled in main region
   - Sample findings generated for practice
   - Findings categorized by severity and mapped to initial triage actions

3. **Billing Guardrail**
   - AWS monthly cost budget created with email alerts
   - Used to ensure experiments with logging/detections stay within safe cost limits

4. **Security Hub**
   - Enabled this week
   - Plan is to integrate findings later in Project B

## What this demonstrates

- I can turn on foundational AWS logging (CloudTrail) in a **cost-aware** and **secure** way.
- I can enable GuardDuty and interpret basic findings (reconnaissance, unauthorized access).
- I think like an entry-level cloud security analyst:
  - “Do we have logs?”
  - “Can we detect suspicious activity?”
  - “Will this blow up the budget?”

## Evidence

All screenshots and notes are under `docs/02-logging-and-visibility/`:

- `notes.md` – setup notes and incident story
- `screenshots/cloudtrail-bucket.png` – S3 logs bucket
- `screenshots/cloudtrail-trail.png` – CloudTrail trail
- `screenshots/cloudtrail-events.png` – Event history
- `screenshots/guardduty-findings.png` – GuardDuty findings list
- `screenshots/guardduty-finding-detail.png` – example finding with details
- `screenshots/billing-budget.png` – AWS monthly cost budget
