# Reality Check: DevSecOps CI/CD Pipeline (`.github/workflows/`)

**Project:** `.github/workflows/trivy-scan.yml`  
**Stack:** GitHub Actions, Trivy, CodeQL, Checkov, TruffleHog, Terraform (GKE, AWS)  
**Summary:** The 4-job security gate was broken in multiple ways simultaneously — all of which were silent. The `trivy-action` version tag didn't exist so all scan jobs were failing, the CodeQL upload action was deprecated, and GKE Terraform had a floating block of invalid HCL that was passing `terraform validate` but failing Checkov parse.

---

## Quick Summary

| Problem | Severity | Time Lost | Status |
| :-- | :-- | :-- | :-- |
| `trivy-action@0.28.0` tag does not exist — all 3 scan jobs silently broken | P1 | Undetected for the entire development period | ✅ Fixed — updated to `@0.30.0` |
| `codeql-action/upload-sarif@v3` deprecated — SARIF uploads failing | P2 | CI warnings accumulating | ✅ Fixed — upgraded to `@v4` |
| Floating `master_authorized_networks_config` block — invalid HCL outside resource | P1 | Caught by Checkov parse error | ✅ Fixed — moved inside `google_container_cluster` |
| GKE cluster missing 6 security controls — Checkov CRITICAL/HIGH findings | P2 | Caught by Checkov | ✅ Fixed — added all supported controls |
| `t2.micro` EBS optimisation false-positive blocked CI | P3 | 30 min | ✅ Fixed — suppressed with justification |

---

## Problem 1 — `trivy-action@0.28.0` Tag Did Not Exist: Security Gate Was Silent

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Critical CI Failure |
| **Time Lost** | Undetected for the entire development period |
| **Discovered** | Reviewing GitHub Actions logs — all Trivy jobs showing "action not found" |

**Symptom:**

All three jobs that used `aquasecurity/trivy-action@0.28.0` failed at the "Set up job" phase — before any code was checked out:

```
Error: Unable to resolve action `aquasecurity/trivy-action@0.28.0`,
the action does not exist on `https://github.com/aquasecurity/trivy-action`.
```

The GitHub Actions dashboard showed all three jobs as "failed," but the failure was in the workflow setup phase, not in the security scan itself. There were no Trivy findings reported — not because there were no findings, but because the scanner never ran.

**Root Cause:**

The `aquasecurity/trivy-action` GitHub Action uses tags for versioning. The tag `0.28.0` did not exist in the `aquasecurity/trivy-action` repository at the time the workflow was written — the actual published tags skip from `0.27.x` to `0.29.x` in that release cycle. This was likely a typo or version extrapolation error.

The critical failure mode: GitHub Actions with a missing action tag fail immediately and silently. There is no fallback, no partial output, no scan results. From the perspective of the repository security dashboard, there are simply no findings — which looks identical to "all scans passed cleanly." A developer reviewing the Security tab would see an empty findings list and conclude the codebase is secure.

The actual state: **security scanning was not running on any commit or pull request for the entire development period.**

**Fix Applied:**

Updated all three Trivy action references to `@0.30.0`, the latest verified-existing release:

```yaml
# Before (broken — tag does not exist):
uses: aquasecurity/trivy-action@0.28.0

# After (fixed — verified existing tag):
uses: aquasecurity/trivy-action@0.30.0
```

Going forward, action versions should be verified by checking the upstream repository's tags page before use, and pinned in the workflow with a comment noting when the pin was last reviewed.

**Business Impact:**

A security gate that silently does not run is worse than no security gate at all — it creates false confidence. Every pull request that was merged during this period was merged without any IaC misconfiguration scanning, container vulnerability scanning, or policy-as-code validation. Any of the issues documented in the other Reality Check files (KMS wildcard policy, unrestricted egress, containers running as root) could have been merged without detection. In a production environment, this is equivalent to a fire alarm that plays a recorded "all clear" message while the building burns.

---

## Problem 2 — `codeql-action/upload-sarif@v3` Deprecated

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — CI Degradation |
| **Time Lost** | Accumulating warning noise; eventual hard failure |
| **Discovered** | GitHub Actions showing deprecation warnings on SARIF upload steps |

**Symptom:**

All three SARIF upload steps were logging:

```
Warning: The `github/codeql-action/upload-sarif` action (v3) is deprecated.
Please update to `github/codeql-action/upload-sarif@v4`.
Support for v3 will be removed on November 1, 2025.
```

After the deprecation date, the steps would begin failing:

```
Error: Action github/codeql-action/upload-sarif@v3 is no longer supported.
Please upgrade to v4.
```

**Root Cause:**

GitHub CodeQL actions follow a major version lifecycle where old versions are actively deprecated and eventually removed. The `v3 → v4` transition included updates to the SARIF schema validation and result deduplication logic. GitHub announced the v3 deprecation in advance, but the warnings in CI were not being actively monitored.

The pattern of "warnings that become errors" is common in CI pipelines: deprecation warnings are easy to ignore when they appear alongside successful output. They only become urgent when the deadline passes and the warning becomes a failure.

**Fix Applied:**

Updated all three SARIF upload references:

```yaml
# Before:
uses: github/codeql-action/upload-sarif@v3

# After:
uses: github/codeql-action/upload-sarif@v4
```

**Business Impact:**

After the deprecation deadline, all SARIF uploads would fail. This means Trivy and Checkov findings would no longer appear in the GitHub Security tab — the centralised view of all vulnerabilities across the repository. Security engineers would lose the aggregated findings view and would need to dig through raw CI logs to find individual scan results. In an enterprise environment with multiple repositories, losing the Security tab view would require significant manual effort to reproduce.

---

## Problem 3 — Floating `master_authorized_networks_config` Block: Invalid HCL

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Invalid Infrastructure Code |
| **Time Lost** | Caught by Checkov parse error |
| **Discovered** | Checkov exiting with parse error on `k8s-ecommerce-project/microservices-demo/terraform/main.tf` |

**Symptom:**

Checkov's scan output included:

```
[ERROR] Failed to parse
  k8s-ecommerce-project/microservices-demo/terraform/main.tf
  terraform parse error: Invalid block definition
  at line 102: A block definition must have block content delimited by "{" and "}",
  starting on the same line as the block header. To define a map element, use the
  equals sign "=" to introduce the element.
```

`terraform validate` on the same file was passing — because `terraform validate` has a broader parser tolerance for some structural errors in newer versions.

**Root Cause:**

The `master_authorized_networks_config` block was sitting at the top level of the file — outside any resource, module, or data block:

```hcl
# ... end of google_container_cluster resource ...
}

# Get credentials for cluster
module "gcloud" { ... }

# PROBLEM: This block was floating here, outside any enclosing resource:
master_authorized_networks_config {
  cidr_blocks {
    cidr_block   = "192.168.49.2/0"
    display_name = "External Access"
  }
}
```

HCL (HashiCorp Configuration Language) does not have top-level named blocks of arbitrary types — only `resource`, `module`, `data`, `variable`, `output`, `locals`, `terraform`, and `provider` are valid top-level block types. `master_authorized_networks_config` is a nested block type that only has meaning inside `google_container_cluster`. Outside that context, it is syntactically invalid.

The block had been cut from inside the `google_container_cluster` resource and pasted below the closing brace, likely during a refactor — but was never restored to its correct position.

**Fix Applied:**

Moved the `master_authorized_networks_config` block back inside the `google_container_cluster` resource, and simultaneously updated the CIDR from an incorrectly-masked `/0` (allows all IPs — equivalent to no restriction) to the correct `/32` (restricts to a single IP):

```hcl
resource "google_container_cluster" "my_cluster" {
  name             = var.name
  location         = var.region
  enable_autopilot = true

  ip_allocation_policy {}

  # Correctly placed inside the cluster resource:
  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = "192.168.49.2/32"       # /32 = single IP; /0 = any IP
      display_name = "External Access"
    }
  }
  # ... other blocks
}
```

The `/0` vs `/32` mistake was a secondary bug discovered while fixing the structural issue: `192.168.49.2/0` is a CIDR that covers all IPs (`/0` has zero fixed bits, matching everything), making the `master_authorized_networks_config` effectively a no-op restriction.

**Business Impact:**

In production, a GKE cluster with `master_authorized_networks_config` using a `/0` CIDR would have its Kubernetes API server exposed to the entire internet — the control plane accessible to any IP. This negates the entire purpose of master authorized networks, which exists specifically to restrict API server access to trusted IPs only. Combined with the floating block being syntactically invalid, this configuration would fail to apply at all on real GKE, meaning the cluster would be provisioned with default (open) API server access.

---

## Problem 4 — GKE Autopilot Cluster Missing 6 Security Controls

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Security Compliance |
| **Time Lost** | ~1 hour applying controls and determining which are Autopilot-managed |
| **Discovered** | Checkov CKV_GCP_12, CKV_GCP_20, CKV_GCP_25, CKV_GCP_61, CKV_GCP_66, CKV_GCP_70 |

**Symptom:**

After fixing the floating block, Checkov reported 6 separate security control failures on the GKE cluster resource.

**Root Cause:**

The original cluster definition was a minimal configuration — only `enable_autopilot = true` and `ip_allocation_policy {}`. GKE Autopilot manages node pools automatically, but cluster-level security controls still require explicit configuration.

The 6 failures fell into two categories:

**Category A — Controls that can and should be configured explicitly:**

| Check | Control | Fix |
| :-- | :-- | :-- |
| CKV_GCP_20 | Master authorized networks | Added `master_authorized_networks_config` block |
| CKV_GCP_25 / CKV_GCP_64 | Private nodes | Added `private_cluster_config` with `enable_private_nodes = true` |
| CKV_GCP_70 | Release channel | Added `release_channel { channel = "REGULAR" }` |
| CKV_GCP_13 | Client certificate disabled | Added `master_auth { client_certificate_config { issue_client_certificate = false } }` |
| CKV_GCP_66 | Binary Authorization | Added `binary_authorization { evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE" }` |
| CKV_GCP_61 | Intranode visibility | Added `enable_intranode_visibility = true` |

**Category B — Controls managed by Autopilot (cannot be manually configured):**

| Check | Why it's Autopilot-managed | Action |
| :-- | :-- | :-- |
| CKV_GCP_12 | Network policy enforcement is automatic in Autopilot; the `network_policy` block is not supported | `#checkov:skip` with justification |
| CKV_GCP_65 | Authenticator groups require a Google Workspace domain not available in this environment | `#checkov:skip` with justification |
| CKV_GCP_69 | Workload metadata config is node-pool-level; Autopilot manages node pools | `#checkov:skip` with justification |

**Business Impact:**

A GKE cluster without private nodes has its node IP addresses publicly routable. A cluster without master authorized networks has its API server accessible to any internet address. A cluster without binary authorization will deploy any container image, including unsigned or tampered images. These are not theoretical risks — each represents a real attack vector that has been exploited in Kubernetes cluster compromises documented in public post-mortems.

---

## Problem 5 — CI Gate Was Reporting "Clean" While Broken

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Meta-Level: The Pipeline Monitoring Itself Was Broken |
| **Time Lost** | The entire development period |
| **Discovered** | All problems above discovered in a single CI review session |

**Symptom:**

The repository showed a CI badge on the README:

```
[![CI/CD](badge.svg)](https://github.com/.../actions/workflows/trivy-scan.yml)
```

The badge was showing the status of the workflow. But the workflow was failing at the action-not-found stage — before any actual scanning occurred. A developer looking at the badge would see "failing" but the failure reason (action tag not found) is fundamentally different from "security vulnerabilities found." The security gate appeared to be working (it was running, reporting status) while being completely ineffective (no scan output produced).

**Root Cause:**

There is a fundamental difference between "workflow executed and reported results" and "workflow executed and produced useful security output." The CI badge conflates these two states. A workflow that fails at `uses: trivy-action@0.28.0` (non-existent) and a workflow that fails because `exit-code: '1'` detected a critical finding both show as "failing" in the badge. A developer monitoring the badge for security signal cannot distinguish between these failure modes without reading the logs.

**Fix Applied:**

Beyond fixing the version tags, added a comment to the workflow documenting the monitoring requirement:

```yaml
# CRITICAL: If this workflow fails at "Set up job" phase rather than the scan phase,
# the failure is a workflow configuration error, NOT a security finding.
# Check: https://github.com/aquasecurity/trivy-action/tags for valid versions.
# Security findings produce failures in the "Run Trivy Scanner" step.
```

**Business Impact:**

In a team or enterprise environment, the security gate is a trust signal. Teams that do not actively monitor why a workflow is failing will either (a) ignore the failure as "CI is always broken" or (b) interpret the failure as a security finding and spend time investigating a non-existent vulnerability. Both outcomes degrade the value of the security gate. The lesson: **the monitoring of security tooling is itself a security concern.**

---

## What These Failures Prove

The DevSecOps pipeline project demonstrated a class of failures that are unique to tooling infrastructure: the tools that are supposed to catch other failures can themselves fail silently.

1. **Action versions must be verified before use** — a non-existent tag produces a silent security gap, not a noisy failure.
2. **Deprecation warnings are future failures** — treating them as noise until they become errors is a maintenance anti-pattern.
3. **`terraform validate` ≠ correct HCL** — plan and validate tools have tolerance for some structural errors; scanners have stricter parsers and will catch what validate misses.
4. **Distinguish "no findings" from "no scans"** — an empty security findings list can mean "all scans passed" or "no scans ran." These look identical in the UI and have completely different meanings.
