# Reality Check: KubeScale Platform (`k8s-ecommerce-project`)

**Project:** `k8s-ecommerce-project/`  
**Stack:** Kubernetes, Minikube, Nginx Ingress, Prometheus, Grafana, HPA, NetworkPolicy, LocalStack, Python (email service)  
**Summary:** Deploying 11 microservices on Kubernetes with full SRE observability encountered four production-grade failures: OOMKill from missing resource limits, NetworkPolicy blocking legitimate service-to-service traffic, Nginx Ingress path routing stripping the `/cart` prefix, and containers running as root failing Trivy scans.

---

## Quick Summary

| Problem | Severity | Time Lost | Status |
| :-- | :-- | :-- | :-- |
| OOMKill crashes — no resource limits set on any pod | P1 | 2 hours debugging | ✅ Fixed — rightsized limits/requests for all services |
| Default-deny NetworkPolicy blocked all inter-service traffic | P1 | 1.5 hours | ✅ Fixed — explicit allow rules per service pair |
| Nginx Ingress stripped `/cart` prefix — 404 on all cart operations | P2 | 1 hour | ✅ Fixed — `nginx.ingress.kubernetes.io/rewrite-target` annotation |
| Containers running as root — Trivy HIGH/CRITICAL findings | P2 | 3 hours | ✅ Fixed — full SecurityContext hardening on all pods |
| LocalStack bridge — K8s pods cannot reach `localhost:4566` | P2 | 45 min | ✅ Fixed — `host.minikube.internal:4566` |

---

## Problem 1 — OOMKill: No Resource Limits Caused Noisy-Neighbour Outages

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Reliability |
| **Time Lost** | ~2 hours debugging random pod restarts |
| **Discovered** | Prometheus dashboard showing `container_oom_events_total` spiking |

**Symptom:**

After deploying all 11 microservices, pods began restarting randomly — with no clear correlation to traffic or time of day. The `kubectl get pods` output showed:

```
NAME                              READY   STATUS      RESTARTS   AGE
frontend-6d4b8f9d4c-x9jkl         1/1     Running     3          45m
checkoutservice-7f8b9c4d5-p2mnq    0/1     OOMKilled   7          45m
recommendationservice-5c6d9-8klmn  1/1     Running     0          45m
```

The `checkoutservice` was being OOMKilled repeatedly. But looking at `kubectl describe pod`, the pod had no resource limits configured:

```
Limits:     <none>
Requests:   <none>
```

**Root Cause:**

Without `resources.limits.memory` on a container, Kubernetes does not impose any memory ceiling. The container can consume as much memory as the node has available. The Google Online Boutique `checkoutservice` (a Go service) has a known memory growth pattern under load due to gRPC connection pool management. Without limits, it would grow until the node's available memory was exhausted, at which point the Linux OOM killer would terminate the process — causing the pod to restart.

The "noisy-neighbour" effect: `checkoutservice`'s unbounded memory consumption was taking memory away from all other pods on the same node, causing cascading degradation even in services that were individually healthy.

**Fix Applied:**

Profiled each service under load using `kubectl top pods` and Grafana, then set rightsized resource requests and limits:

```yaml
resources:
  requests:
    cpu: "100m"       # Guaranteed scheduling allocation
    memory: "128Mi"   # Baseline memory reservation
  limits:
    cpu: "200m"       # Hard ceiling (throttled, not killed)
    memory: "256Mi"   # Hard ceiling (OOMKill if exceeded)
```

The HPA was then configured to scale out when memory utilisation exceeded 80% of the limit — triggering scale-out before any single pod was OOMKilled.

**Business Impact:**

OOMKill is a full-process restart — equivalent to a crash. For a checkout service, each OOMKill is a potential lost transaction and a cart abandonment. At scale, 7 restarts in 45 minutes would translate to 7 lost checkout windows of 10–30 seconds each, during which users receive 502 errors. In an e-commerce context with high cart values, each lost checkout window is direct revenue loss. Resource limits are not optional in production.

---

## Problem 2 — Default-Deny NetworkPolicy Broke All Inter-Service Communication

| Field | Value |
| :-- | :-- |
| **Severity** | P1 — Complete Outage |
| **Time Lost** | ~1.5 hours |
| **Discovered** | Immediately after applying `network-policy.yaml` — all services returned 502 |

**Symptom:**

After applying the NetworkPolicy manifest to enforce zero-trust networking, all services in the cluster became unreachable. `curl http://shop.local` returned:

```
502 Bad Gateway
```

`kubectl logs frontend-*` showed:

```
failed to connect to cartservice:7070 — connection refused
failed to connect to productcatalogservice:3550 — no route to host
```

**Root Cause:**

The NetworkPolicy was configured with a correct zero-trust posture: `podSelector: {}` (select all pods) with no `ingress` or `egress` rules, which in Kubernetes means **deny all traffic for all pods in the namespace**.

```yaml
# This is correct zero-trust posture...
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
spec:
  podSelector: {}    # Applies to all pods
  policyTypes:
    - Ingress
    - Egress
  # No ingress/egress rules = deny all
```

The problem: the explicit allow rules for each service-to-service path were added in a separate policy that referenced the wrong `podSelector` labels. The label on `cartservice` pods was `app: cartservice`, but the NetworkPolicy was selecting on `app: cart-service` (with a hyphen vs underscore inconsistency).

**Fix Applied:**

Audited all pod labels with `kubectl get pods --show-labels` and cross-referenced against each NetworkPolicy selector. Corrected all label mismatches:

```yaml
# Explicit allow: frontend → cartservice on port 7070
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-cartservice
spec:
  podSelector:
    matchLabels:
      app: cartservice    # Must match the actual pod label exactly
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: frontend
      ports:
        - port: 7070
```

**Business Impact:**

A default-deny NetworkPolicy applied to a production cluster without pre-validated allow rules causes an immediate total outage — 100% of traffic is blocked, including health checks, liveness probes, and all service-to-service calls. Kubernetes will begin restarting unhealthy pods that fail their liveness probes, creating a cascade that looks like a cluster-level failure. The fix requires both correcting the policy and waiting for pod restarts to clear — a recovery process that takes 5–10 minutes minimum. In production, this is a SEV-1 incident with an SLA breach.

---

## Problem 3 — Nginx Ingress Stripped `/cart` Path Prefix: 404 on All Cart Operations

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Functional Bug |
| **Time Lost** | ~1 hour |
| **Discovered** | `curl http://shop.local/cart` returned 404 from `cartservice` |

**Symptom:**

The Nginx Ingress was configured to route `/cart` to `cartservice:80`. The request reached the pod but `cartservice` returned:

```
HTTP 404 Not Found
path /cart not found
```

The cartservice expected requests at `/` (its root), not at `/cart`.

**Root Cause:**

Nginx Ingress routes traffic based on the `path` field in the Ingress rule. When the request matches `/cart`, Nginx forwards the request **including the `/cart` prefix** to the backend service by default. So `cartservice` received a request for `/cart`, but its route handlers were registered at `/` (the root path).

The fix requires a rewrite rule that strips the matching prefix before forwarding.

**Fix Applied:**

Added the `rewrite-target` annotation to the Ingress:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: shop-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2    # Strip the matched path
spec:
  rules:
    - host: shop.local
      http:
        paths:
          - path: /cart(/|$)(.*)    # Capture group for rewrite
            pathType: ImplementationSpecific
            backend:
              service:
                name: cartservice
                port:
                  number: 80
```

The `/$2` in `rewrite-target` strips the `/cart` prefix and forwards only the remainder of the path to `cartservice`.

**Business Impact:**

In a production e-commerce application, a broken `/cart` endpoint means users cannot view or modify their shopping cart. Every product page that calls the cart API (for item counts, add-to-cart buttons) would receive errors. This is the highest-impact single endpoint after the checkout flow — broken cart functionality translates directly to abandoned purchases. The Nginx path rewrite pattern is non-obvious and not prominently documented; it is a frequent source of production routing bugs in Kubernetes.

---

## Problem 4 — Containers Running as Root: HIGH/CRITICAL Trivy Findings

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Security |
| **Time Lost** | ~3 hours across all 11 services |
| **Discovered** | Trivy IaC scan in CI pipeline on first PR |

**Symptom:**

The initial Trivy scan of the email service Kubernetes manifest returned:

```
HIGH: Container running as root user — add 'runAsNonRoot: true' to securityContext
HIGH: Container allows privilege escalation — set 'allowPrivilegeEscalation: false'
CRITICAL: Container has no read-only root filesystem — set 'readOnlyRootFilesystem: true'
HIGH: Container capabilities not dropped — add 'capabilities.drop: [ALL]'
```

Four findings per container × 11 services = 44 initial findings.

**Root Cause:**

Docker containers run as root by default. The Google Online Boutique upstream manifests do not include security contexts — they are designed as a demo application, not a production security baseline. Every manifest in the `kubernetes-manifests/` directory had no `securityContext` at all.

Running as root means:
- A container escape bug gives root access to the node
- Malware within the container can write anywhere on the filesystem
- Privilege escalation within the container is trivial (any `setuid` binary works)

**Fix Applied:**

Applied the hardening baseline from ADR-003 to all container manifests:

```yaml
securityContext:                          # Pod-level
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 3000
  fsGroup: 2000
  seccompProfile:
    type: RuntimeDefault
containers:
  - name: email-service
    securityContext:                      # Container-level
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true
      capabilities:
        drop: [ALL]
```

The custom `email-service` Dockerfile was updated to add a non-root user:

```dockerfile
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser
```

After applying the hardening, Trivy reported **0 HIGH/CRITICAL findings**.

**Business Impact:**

In a production Kubernetes cluster, a single compromised container running as root can pivot to control the entire node (via container escape vulnerabilities, which appear regularly in the CVE feed). From node compromise, an attacker can access the kubelet credentials and escalate to cluster admin. The entire 11-service platform can be compromised via a single vulnerability in one service. Running non-root with a read-only filesystem reduces the blast radius from "entire cluster" to "one container."

---

## Problem 5 — LocalStack Bridge: K8s Pods Cannot Reach `localhost:4566`

| Field | Value |
| :-- | :-- |
| **Severity** | P2 — Development Environment |
| **Time Lost** | ~45 minutes |
| **Discovered** | `email-service` pod logs showed `ConnectionRefusedError: [Errno 111] localhost:4566` |

**Symptom:**

The email service needed to call LocalStack's SES API to send emails. The SDK was configured to use `http://localhost:4566` as the endpoint. Inside the Minikube cluster, the pod's `localhost` is the pod's loopback interface — not the host machine's loopback. LocalStack was running on the host machine.

**Root Cause:**

`localhost` inside a Kubernetes pod refers to the pod's own loopback network interface (`127.0.0.1`). LocalStack is running as a Docker container on the host machine. The host machine's `localhost` is not reachable from inside the Kubernetes pod network.

Minikube provides a special DNS name `host.minikube.internal` that resolves to the host machine's IP from within pods — the correct bridge for host-to-cluster communication.

**Fix Applied:**

Updated the SDK endpoint configuration in the email service to use the Minikube bridge:

```python
# Wrong — pod's localhost, not the host machine's localhost
endpoint_url = "http://localhost:4566"

# Correct — Minikube bridge to host machine
endpoint_url = "http://host.minikube.internal:4566"
```

This was added as a conditional based on the `ENVIRONMENT` environment variable so the same code works in production (real AWS, no endpoint override) and in development (LocalStack via Minikube bridge).

**Business Impact:**

In production, this issue doesn't exist — the SDK calls real AWS endpoints without any override. The lesson is about dev/prod parity: the development environment must faithfully simulate the production network topology. When it doesn't, bugs hide in the gap between environments and only surface in production. A systematic approach (always using environment variables for endpoint overrides) ensures the production code path and the development code path diverge only in configuration, not in logic.

---

## What These Failures Prove

The KubeScale project's failures cluster into three categories:

1. **Kubernetes operational fundamentals** — OOMKill (missing resource limits), NetworkPolicy label mismatch, and Ingress path rewriting are the three most common sources of Kubernetes production incidents in teams new to K8s. Encountering and resolving them in a controlled environment builds the diagnostic pattern recognition required for on-call response.

2. **Security-as-default requires active effort** — Containers default to root, NetworkPolicy defaults to allow-all, and Trivy reports none of this unless explicitly run. Adding security posture to a system requires scanning, reviewing findings, and systematically applying controls — it does not happen automatically.

3. **Dev/prod environment gap requires deliberate bridging** — The LocalStack bridge issue is a microcosm of a broader pattern: development environments that differ from production in network topology, authentication, or API behaviour hide bugs that only appear in production. The solution is systematic: use environment variables for all environment-specific configuration, and keep the code path identical.
