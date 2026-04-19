# Week 2 — Logging, Detections & Visibility

## 1. CloudTrail Setup

- S3 bucket created for logs:
  - Name: `afsod-cloudtrail-logs-12345`
  - Region: `eu-east-1`
  - Public access: BLOCKED (all 4 options enabled)

- Trail created:
  - Name: `afsod-security-trail`
  - Scope: Management events (Read + Write), single region only
  - Data events: Disabled (to control cost at this stage)
  - Destination: S3 bucket above

- Verification:
  - Opened Event history and saw events like `StartLogging`, `CreateTrail`, `ConsoleLogin`
  - This proves CloudTrail is recording management activity

- Why this matters for a junior cloud security role:
  - CloudTrail is the main audit log – you use it to investigate “who did what, when, and from where”.
  - Keeping it in a private S3 bucket is critical so attackers can’t delete or read your logs.
  - It is a foundational service for security monitoring and incident response.

  ## 2. Billing Guardrail

- Created a monthly cost budget for: $10
- Alerts:
  - 50%, 80% and 100%thresholds send an email to me
- Purpose:
  - Ensure CloudTrail/GuardDuty or other tests never silently run up large bills

## 3. GuardDuty Setup and Findings

- Enabled GuardDuty in region: `eu-east-1`
- Generated sample findings from the console

Findings observed:
- `UnauthorizedAccess:IAMUser/RootCredentialUsage`
    - Severity: LOW
    - Meaning: The GuardDuty `GetFindingsStatistics` API was invoked using the AWS root account credentials
    - Possible actions: Stop using root for everyday tasks, create and use IAM users/roles instead, enable MFA on the root account, review CloudTrail for other root activity

- `UnauthorizedAccess:IAMUser/InstanceCredentialExfiltration`
  - Severity: HIGH
  - Meaning: Instance credentials may have been used from an unusual location
  - Possible actions: Rotate credentials, review CloudTrail, lock or delete compromised user/role

 - `Recon:EC2/PortProbeUnprotectedPort` (This is a good one to know, as it's a common finding, and often indicates a precursor to an attack)
   - Severity: MEDIUM
   - Meaning: Someone is scanning an EC2 instance for open ports
   - Possible actions: Check security groups, restrict exposed ports, review access logs

Simple triage rule I will use:
- HIGH → investigate immediately, block or rotate credentials, isolate affected resources
- MEDIUM → investigate soon, correlate with CloudTrail to see who did what
- LOW → monitor patterns, possibly improve configuration later

## 4. Security Hub (Overview)

- Purpose: Central dashboard that aggregates findings from services like GuardDuty, IAM, Config, etc.
- Current status:
  - Enabled in my main region with default security standards

- How I plan to use it later:
  - Link GuardDuty + CloudTrail + Security Hub in Project B
  - Use it as a “single pane of glass” for security posture.

## 5. Practice Incident Story (CloudTrail + GuardDuty)

Scenario:
- GuardDuty finding: `UnauthorizedAccess:IAMUser/RootCredentialUsage`

Triage steps:
1. In GuardDuty, note time, source IP, account, and severity. (This is the initial alert.)
2. In CloudTrail, filter around that time for `userIdentity: Root` and risky API calls. (To understand what the root user did.)
3. Match IP and actions against known locations and normal activity. (To determine if it's expected or not.)
4. Decide if activity is legitimate, accidental, or suspicious. (The conclusion of the triage.)

Responses:
- Stop using root for routine tasks; enable MFA on root.
- Rotate any exposed credentials.
- Add alarms for root usage and critical policy/network changes.
- Record timeline, impact, and actions in an incident log/runbook.

  


