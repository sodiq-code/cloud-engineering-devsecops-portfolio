# ADR-003: Container Security Hardening Baseline (Zero-Finding Standard)

**Date:** 2025-11-15  
**Status:** Accepted  
**Deciders:** Jimoh Sodiq Bolaji  
**Category:** Container Security / DevSecOps

---

## Context

By default, Docker containers run as root and have full access to the host kernel's capability set. This is a critical security risk:
- A container escape bug gives root access to the host
- Malware can write to any filesystem location
- Privilege escalation within the container is trivial

Trivy scans of default containers produced HIGH/CRITICAL findings.

## Decision

Enforce the following hardening baseline on **all container manifests** in this portfolio. This baseline achieves a **0-finding result** in Aqua Security Trivy IaC scans.

### Kubernetes Pod/Container Spec Baseline

```yaml
securityContext:                         # Pod-level
  runAsNonRoot: true
  runAsUser: 1000
  runAsGroup: 3000
  fsGroup: 2000
  seccompProfile:
    type: RuntimeDefault

containers:
  - securityContext:                     # Container-level
      allowPrivilegeEscalation: false
      runAsNonRoot: true
      runAsUser: 1000
      readOnlyRootFilesystem: true
      capabilities:
        drop:
          - ALL
```

### Dockerfile Baseline

```dockerfile
FROM python:3.9.18-slim              # Pinned version + slim base
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser                         # Non-root execution
CMD ["gunicorn", "app:app"]          # Production WSGI server
```

## Consequences

### Positive
- ✅ Passes Trivy IaC scan with 0 HIGH/CRITICAL findings
- ✅ Principle of Least Privilege enforced at container level
- ✅ Limits blast radius of container escape vulnerabilities
- ✅ `readOnlyRootFilesystem` prevents malware from writing to disk

### Negative / Compatibility
- ⚠️ `readOnlyRootFilesystem: true` requires apps to use `emptyDir` volumes for temp files
- ⚠️ Some legacy images are built to run as root — require Dockerfile modifications
- ⚠️ `capabilities: drop: ALL` may break apps that need specific capabilities (e.g., `NET_BIND_SERVICE` for port 80)

### Mitigation
- Add `volumeMounts` with `emptyDir` for `/tmp` in any container using the read-only root filesystem
- Re-add specific capabilities individually only if absolutely required: `add: [NET_BIND_SERVICE]`

## Alternatives Considered

| Option | Reason Not Chosen |
| :--- | :--- |
| OPA/Gatekeeper policies | Adds complexity; baseline is simpler and sufficient for this project scope |
| Kata Containers (VM isolation) | Requires hardware; LocalStack/Minikube environment does not support it |
| AppArmor profiles | Platform-specific; not portable across all Kubernetes distributions |
