# Operations Runbook - Legal Events Production

**Version**: 1.0.0  
**Last Updated**: November 9, 2025  
**Status**: Production Operations Guide

---

## 📋 Table of Contents

1. [Worker Health Monitoring & Troubleshooting](#worker-health-monitoring--troubleshooting)
2. [Understanding Worker Status](#understanding-worker-status)
3. [Status States](#status-states)
4. [Heartbeat Semantics](#heartbeat-semantics)
5. [Troubleshooting Degraded Status](#troubleshooting-degraded-status)
6. [Monitoring & Alerting Setup](#monitoring--alerting-setup)
7. [Escalation Path](#escalation-path)

---

## Worker Health Monitoring & Troubleshooting

### Understanding Worker Status

The system provides two monitoring endpoints:

1. **`GET /health`** - Basic health check
   - Only checks if workers are registered (`workers_registered > 0`)
   - Does NOT validate heartbeat liveness
   - Use for high-level system health only

2. **`GET /v1/workers/status`** - Detailed worker health (RECOMMENDED)
   - Heartbeat-aware liveness detection
   - Detects stale workers (no heartbeat for >60s)
   - Provides per-worker heartbeat details

---

## Status States

| Status | Condition | Severity | Action Required |
|--------|-----------|----------|-----------------|
| `healthy` | All workers have active heartbeats | None | None |
| `degraded` | No workers, zero heartbeats, or stale heartbeats | Warning | Investigate immediately |
| `unhealthy` | Endpoint error (exception path) | Error | System malfunction |

---

## Heartbeat Semantics

- **Heartbeat Interval**: 10 seconds (worker/main.py)
- **Heartbeat TTL**: 30 seconds (worker/main.py)
- **Stale Threshold**: Heartbeat older than 60 seconds (infra/queue.py)
- **Healthy Criteria**: `workers_registered > 0` AND `workers_with_heartbeat > 0` AND `workers_stale == 0`

---

## Troubleshooting Degraded Status

### Scenario 1: `status == "degraded"` AND `workers_with_heartbeat == 0`

**Symptoms:**
```json
{
  "workers_registered": 2,
  "workers_with_heartbeat": 0,
  "workers_stale": 0,
  "healthy": false,
  "status": "degraded"
}
```

**Root Cause**: Workers registered but not publishing heartbeats (startup failure, network issues, or heartbeat mechanism disabled).

**Investigation Steps:**

1. **Check worker container status:**
   ```bash
   docker compose ps worker
   docker logs legal_events_worker --tail 100
   ```

2. **Inspect Redis heartbeats manually:**
   ```bash
   # List all heartbeat keys
   docker exec legal_events_redis redis-cli KEYS "worker:heartbeat:*"
   
   # Check specific heartbeat TTL
   docker exec legal_events_redis redis-cli TTL "worker:heartbeat:<worker-id>"
   
   # Get heartbeat data
   docker exec legal_events_redis redis-cli GET "worker:heartbeat:<worker-id>"
   ```

3. **Verify worker heartbeat configuration:**
   - Check worker/main.py heartbeat emission (emits every 10s, TTL 30s)
   - Verify Redis connectivity from worker

4. **Check for worker process crashes:**
   ```bash
   docker compose logs worker | grep -i "error\|exception\|crash"
   ```

**Resolution:**
```bash
# Restart worker container
docker compose restart worker

# Full cleanup and restart if needed
docker compose down worker
docker compose up -d worker
```

---

### Scenario 2: `status == "degraded"` AND `workers_stale > 0`

**Symptoms:**
```json
{
  "workers_registered": 2,
  "workers_with_heartbeat": 1,
  "workers_stale": 1,
  "healthy": false,
  "status": "degraded"
}
```

**Root Cause**: Some workers stopped publishing heartbeats (crashed, hung, or network partition).

**Investigation Steps:**

1. **Clean up stale workers:**
   ```bash
   curl -X POST http://localhost:8000/v1/workers/cleanup
   ```
   This removes workers with heartbeats >60s old.

2. **Check which workers are stale:**
   ```bash
   curl http://localhost:8000/v1/workers/status | jq '.workers[] | select(.heartbeat.is_alive == false)'
   ```

3. **Inspect container status:**
   ```bash
   docker compose ps | grep worker
   ```

**Resolution:**
- Run cleanup endpoint (POST /v1/workers/cleanup)
- If workers don't recover, restart: `docker compose restart worker`

---

### Scenario 3: `status == "degraded"` AND `workers_registered == 0`

**Symptoms:**
```json
{
  "workers_registered": 0,
  "workers_with_heartbeat": 0,
  "workers_stale": 0,
  "healthy": false,
  "status": "degraded"
}
```

**Root Cause**: No workers running at all.

**Investigation Steps:**

1. **Check worker container:**
   ```bash
   docker compose ps worker
   docker compose logs worker --tail 50
   ```

2. **Check for startup errors:**
   ```bash
   docker compose logs worker | grep -i "error\|failed\|exception"
   ```

**Resolution:**
```bash
# Start worker if stopped
docker compose up -d worker

# Or restart if running but not registering
docker compose restart worker
```

---

## Monitoring & Alerting Setup

### Recommended Alert Rules

**Alert Rule 1: Worker Degraded State**
```yaml
alert: WorkersDegraded
expr: worker_status_healthy == 0 OR worker_status != "healthy"
for: 2m  # Alert after 2 consecutive check failures
severity: warning
annotations:
  summary: "Workers in degraded state"
  description: "healthy={{ .healthy }}, status={{ .status }}, workers_with_heartbeat={{ .workers_with_heartbeat }}"
```

**Alert Rule 2: No Active Workers**
```yaml
alert: NoActiveWorkers
expr: worker_status_workers_with_heartbeat == 0
for: 1m
severity: critical
annotations:
  summary: "No workers with active heartbeats"
  description: "System cannot process documents"
```

**Alert Rule 3: Stale Workers Detected**
```yaml
alert: StaleWorkersDetected
expr: worker_status_workers_stale > 0
for: 5m
severity: warning
annotations:
  summary: "Stale workers detected"
  description: "{{ .workers_stale }} worker(s) have stale heartbeats (>60s)"
```

---

### Monitoring Script Example

```bash
#!/bin/bash
# check_worker_health.sh
# Nagios-compatible health check script

STATUS=$(curl -s http://localhost:8000/v1/workers/status)
HEALTHY=$(echo "$STATUS" | jq -r '.healthy')
STATUS_STR=$(echo "$STATUS" | jq -r '.status')
WORKERS_WITH_HEARTBEAT=$(echo "$STATUS" | jq -r '.workers_with_heartbeat')
WORKERS_STALE=$(echo "$STATUS" | jq -r '.workers_stale')

if [ "$HEALTHY" != "true" ] || [ "$STATUS_STR" != "healthy" ]; then
  echo "CRITICAL: Workers degraded - healthy=$HEALTHY, status=$STATUS_STR, active=$WORKERS_WITH_HEARTBEAT, stale=$WORKERS_STALE"
  exit 2  # Nagios CRITICAL
fi

echo "OK: Workers healthy - active=$WORKERS_WITH_HEARTBEAT, stale=$WORKERS_STALE"
exit 0  # Nagios OK
```

**Installation:**
```bash
# Save script
sudo cp check_worker_health.sh /usr/local/bin/
sudo chmod +x /usr/local/bin/check_worker_health.sh

# Test
/usr/local/bin/check_worker_health.sh
```

---

### Continuous Monitoring Script

```bash
#!/bin/bash
# monitor_workers.sh
# Continuous monitoring with logging

LOG_FILE="/var/log/worker_health.log"

while true; do
  TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  STATUS=$(curl -s http://localhost:8000/v1/workers/status)
  HEALTHY=$(echo "$STATUS" | jq -r '.healthy')
  STATUS_STR=$(echo "$STATUS" | jq -r '.status')
  
  if [ "$HEALTHY" != "true" ]; then
    echo "$TIMESTAMP - ALERT: Workers degraded - $STATUS" | tee -a "$LOG_FILE"
    # Send alert (integrate with PagerDuty, Slack, etc.)
  else
    echo "$TIMESTAMP - OK: Workers healthy" >> "$LOG_FILE"
  fi
  
  sleep 60  # Check every minute
done
```

---

## Escalation Path

### Response Times

1. **status == "degraded"**: 
   - Investigate within 5 minutes
   - Page on-call engineer if persists >10 minutes
   - Severity: P2 (High)

2. **status == "unhealthy"**: 
   - Immediate page to on-call engineer
   - Critical system malfunction
   - Severity: P1 (Critical)

3. **workers_with_heartbeat == 0**:
   - Investigate within 2 minutes
   - Page on-call if not resolved in 5 minutes
   - Severity: P1 (Critical) - System cannot process documents

---

## Health Check Comparison

| Check | Endpoint | Heartbeat-Aware | Recommended For |
|-------|----------|-----------------|-----------------|
| Basic | GET /health | ❌ No | Load balancer health checks |
| Detailed | GET /v1/workers/status | ✅ Yes | Monitoring/alerting systems |

---

## Quick Reference Commands

### Check Worker Status
```bash
# Get worker status
curl http://localhost:8000/v1/workers/status | jq

# Check if healthy
curl -s http://localhost:8000/v1/workers/status | jq '.healthy, .status'

# Count active workers
curl -s http://localhost:8000/v1/workers/status | jq '.workers_with_heartbeat'

# Show stale workers
curl -s http://localhost:8000/v1/workers/status | jq '.workers[] | select(.heartbeat.is_alive == false)'
```

### Cleanup Commands
```bash
# Clean up stale workers
curl -X POST http://localhost:8000/v1/workers/cleanup

# Restart worker service
docker compose restart worker

# View worker logs
docker compose logs worker --tail 100 -f
```

### Redis Inspection
```bash
# List all worker heartbeats
docker exec legal_events_redis redis-cli KEYS "worker:heartbeat:*"

# Check heartbeat TTL
docker exec legal_events_redis redis-cli TTL "worker:heartbeat:<worker-id>"

# Get heartbeat value
docker exec legal_events_redis redis-cli GET "worker:heartbeat:<worker-id>"

# List all workers (RQ native)
docker exec legal_events_redis redis-cli SMEMBERS "rq:workers"
```

---

## Related Documentation

- [Worker Status API Reference](LEGAL_EVENTS_CODE_MAP.md#worker-status-endpoint-heartbeat-aware)
- [RUN54 Implementation Summary](RUN54_IMPLEMENTATION_SUMMARY.md)
- [Service Boundaries](SERVICE_BOUNDARIES.md)
- [Security Setup](SECURITY_SETUP.md)

---

## Support & Contact

For operational issues or questions:
- Review this runbook first
- Check [LEGAL_EVENTS_CODE_MAP.md](LEGAL_EVENTS_CODE_MAP.md) for system architecture
- File issues at: https://github.com/molotovsingh/legal_events_prod/issues
