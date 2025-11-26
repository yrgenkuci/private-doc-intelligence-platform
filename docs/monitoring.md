# Grafana Dashboards Guide

This guide covers setting up Grafana dashboards for visualizing metrics from the Document Intelligence Platform.

## Overview

We've created two production-grade Grafana dashboards:
1. **API Overview Dashboard** - HTTP metrics, latency, errors
2. **Document Processing Dashboard** - Upload metrics, OCR performance

## What is Grafana?

**Grafana** is an open-source visualization and analytics platform that allows you to:
- Query, visualize, and understand your metrics
- Create alerts based on metric thresholds
- Build beautiful, interactive dashboards
- Share dashboards with your team

**Think of it as:** A powerful GUI for your Prometheus metrics - turning raw numbers into meaningful visualizations.

## Prerequisites

- Kubernetes cluster with Prometheus Operator installed
- Prometheus collecting metrics from our services
- Metrics exposed on `/metrics` endpoint (Step 10 complete)

## Quick Start

### Option 1: Using kube-prometheus-stack (Recommended)

The easiest way to get Grafana with Prometheus integration:

```bash
# Add Prometheus community Helm repo
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Install kube-prometheus-stack (includes Grafana + Prometheus + Alertmanager)
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set grafana.adminPassword=admin
```

**What this gives you:**
- - Grafana pre-configured with Prometheus data source
- - Default Kubernetes dashboards
- - Alertmanager for notifications
- - Service monitors already configured

### Option 2: Standalone Grafana Installation

If you already have Prometheus:

```bash
# Add Grafana Helm repo
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

# Install Grafana
helm install grafana grafana/grafana \
  --namespace monitoring \
  --create-namespace \
  --set adminPassword=admin \
  --set datasources."datasources\.yaml".apiVersion=1 \
  --set datasources."datasources\.yaml".datasources[0].name=Prometheus \
  --set datasources."datasources\.yaml".datasources[0].type=prometheus \
  --set datasources."datasources\.yaml".datasources[0].url=http://prometheus-kube-prometheus-prometheus:9090 \
  --set datasources."datasources\.yaml".datasources[0].access=proxy \
  --set datasources."datasources\.yaml".datasources[0].isDefault=true
```

## Accessing Grafana

### Port Forward (for testing)

```bash
# Get Grafana pod
kubectl get pods -n monitoring | grep grafana

# Port forward
kubectl port-forward -n monitoring svc/prometheus-grafana 3000:80
# Or for standalone: kubectl port-forward -n monitoring svc/grafana 3000:80

# Access Grafana
open http://localhost:3000
```

**Default credentials:**
- Username: `admin`
- Password: `admin` (or what you set during install)

### Production Access (via Ingress)

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: grafana-ingress
  namespace: monitoring
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  rules:
    - host: grafana.yourdomain.com
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: prometheus-grafana
                port:
                  number: 80
```

## Importing Our Dashboards

### Method 1: Via Grafana UI (Learning Mode)

1. **Login to Grafana** at http://localhost:3000

2. **Navigate to Dashboards:**
   - Click on the "+" icon in left sidebar
   - Select "Import"

3. **Import API Overview Dashboard:**
   - Click "Upload JSON file"
   - Select `k8s/base/grafana/dashboards/api-overview.json`
   - Click "Load"
   - Select "Prometheus" as data source
   - Click "Import"

4. **Import Document Processing Dashboard:**
   - Repeat for `k8s/base/grafana/dashboards/document-processing.json`

5. **View Dashboards:**
   - Click "Dashboards" in left sidebar
   - You'll see both dashboards listed
   - Click to open and explore!

### Method 2: Via Kubernetes ConfigMaps (Production)

For automatic dashboard provisioning:

```bash
# Create ConfigMaps from dashboard JSON files
kubectl create configmap grafana-dashboard-api-overview \
  --from-file=k8s/base/grafana/dashboards/api-overview.json \
  -n monitoring \
  --dry-run=client -o yaml | kubectl apply -f -

kubectl create configmap grafana-dashboard-document-processing \
  --from-file=k8s/base/grafana/dashboards/document-processing.json \
  -n monitoring \
  --dry-run=client -o yaml | kubectl apply -f -

# Label ConfigMaps for Grafana to discover them
kubectl label configmap grafana-dashboard-api-overview \
  grafana_dashboard=1 -n monitoring

kubectl label configmap grafana-dashboard-document-processing \
  grafana_dashboard=1 -n monitoring

# Restart Grafana to pick up dashboards
kubectl rollout restart deployment prometheus-grafana -n monitoring
```

**How it works:**
- Grafana watches for ConfigMaps with label `grafana_dashboard=1`
- Automatically loads JSON from ConfigMaps
- Dashboards appear in Grafana UI within 30 seconds

## Understanding the Dashboards

### Dashboard 1: API Overview

**Purpose:** Monitor HTTP API health and performance

**Panels:**

1. **Request Rate by Endpoint** (Graph)
   - Query: `sum(rate(http_requests_total[5m])) by (endpoint)`
   - Shows: Requests per second for each endpoint
   - Use: Identify high-traffic endpoints

2. **95th Percentile Latency** (Gauge)
   - Query: `histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))`
   - Shows: 95% of requests complete within this time
   - Thresholds:
     - Green: < 0.5s
     - Yellow: 0.5s - 1s
     - Red: > 1s

3. **Error Rate (5xx)** (Graph)
   - Query: `sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))`
   - Shows: Percentage of failed requests
   - Use: Detect service degradation

4. **Request Duration Percentiles** (Graph)
   - Queries: p50, p95, p99 latencies
   - Shows: Latency distribution over time
   - Use: Understand typical vs worst-case performance

**Key Metrics to Watch:**
- Request rate should be stable (no sudden drops = service down)
- P95 latency should be < 1s
- Error rate should be < 1%

### Dashboard 2: Document Processing

**Purpose:** Monitor document uploads and OCR performance

**Panels:**

1. **Total Documents Uploaded** (Stat)
   - Query: `sum(documents_uploaded_total)`
   - Shows: Cumulative upload count
   - Use: Track usage over time

2. **Upload Success Rate** (Gauge)
   - Query: `sum(rate(documents_uploaded_total{status="success"}[5m])) / sum(rate(documents_uploaded_total[5m])) * 100`
   - Shows: Percentage of successful uploads
   - Thresholds:
     - Red: < 90%
     - Yellow: 90-95%
     - Green: > 95%

3. **Document Upload Size** (Graph)
   - Queries: Average and p95 file sizes
   - Shows: Upload size distribution
   - Use: Understand typical document sizes

4. **OCR Request Rate** (Graph)
   - Queries: Success vs failed OCR requests
   - Shows: OCR processing volume
   - Use: Monitor OCR service health

5. **OCR Processing Duration** (Graph)
   - Queries: p50, p95, p99 processing times
   - Shows: How long OCR takes
   - Thresholds:
     - Green: < 2s
     - Yellow: 2-5s
     - Red: > 5s

**Key Metrics to Watch:**
- Success rate should be > 95%
- OCR p95 duration should be < 5s
- Failed OCR requests should be investigated

## Understanding Dashboard Components

### Panel Types

**1. Time Series (Graph)**
- Shows data over time
- Best for: trends, rates, patterns
- Example: Request rate over last hour

**2. Gauge**
- Shows single value with thresholds
- Best for: percentages, current status
- Example: Error rate (with green/yellow/red zones)

**3. Stat**
- Shows single number with sparkline
- Best for: totals, counts
- Example: Total documents uploaded

### PromQL Queries Explained

**Basic query:**
```promql
http_requests_total
```
- Shows all HTTP requests (raw counter)

**Rate (requests per second):**
```promql
rate(http_requests_total[5m])
```
- Shows rate of increase over 5 minutes
- Converts counter to per-second rate

**Sum by label:**
```promql
sum(rate(http_requests_total[5m])) by (endpoint)
```
- Groups by endpoint
- Shows separate line for each endpoint

**Percentile (histogram):**
```promql
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))
```
- Calculates 95th percentile
- 95% of requests are faster than this value

**Division (ratio):**
```promql
sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
```
- Divides errors by total requests
- Shows error rate as fraction

## Customizing Dashboards

### Adding a New Panel

1. Click **"Add panel"** at top of dashboard
2. Select **"Add a new panel"**
3. **Build query:**
   - Data source: Prometheus
   - Enter PromQL query (e.g., `rate(my_metric[5m])`)
4. **Choose visualization:**
   - Time series, Gauge, Stat, Table, etc.
5. **Configure panel:**
   - Title, description
   - Thresholds (color zones)
   - Legend format
   - Units (seconds, bytes, percent, etc.)
6. Click **"Apply"**

### Editing Existing Panel

1. Click panel title
2. Select **"Edit"**
3. Modify query or visualization
4. Click **"Apply"**

### Setting Thresholds

In panel edit mode:
1. Go to **"Field"** tab on right
2. Scroll to **"Thresholds"**
3. Add threshold values:
   - Base: 0 (green)
   - Threshold 1: 0.5 (yellow)
   - Threshold 2: 1 (red)
4. Colors apply based on value ranges

## Best Practices

### Dashboard Design

- **Do:**
- Group related metrics together
- Use consistent color schemes
- Add panel descriptions
- Set appropriate time ranges
- Use meaningful panel titles

- **Don't:**
- Overcrowd with too many panels (max 8-12)
- Use misleading scales
- Forget to add units
- Mix unrelated metrics

### Query Optimization

- **Efficient queries:**
```promql
# Good: Aggregates before rate
sum(rate(metric[5m])) by (label)

# Good: Uses specific labels
metric{endpoint="/api/v1/upload"}
```

- **Avoid:**
```promql
# Bad: Rate before aggregation (slower)
rate(sum(metric)[5m])

# Bad: Regex on high-cardinality labels
metric{user_id=~".*"}
```

### Time Ranges

- **Real-time monitoring:** Last 5-15 minutes
- **Recent trends:** Last 1-6 hours
- **Daily patterns:** Last 24 hours
- **Weekly analysis:** Last 7 days

## Alerting (Advanced)

### Creating an Alert

1. Edit a panel
2. Go to **"Alert"** tab
3. Click **"Create alert rule from this panel"**
4. Configure:
   - **Condition:** When value is above/below threshold
   - **Evaluation:** How often to check
   - **For:** How long condition must be true
5. Add **notification channel** (email, Slack, etc.)
6. Save alert

### Example Alert Rules

**High Error Rate:**
```yaml
Alert: HighErrorRate
Condition: error_rate > 0.05  # 5%
For: 5m
Severity: warning
Message: "API error rate is {{ $value }}%"
```

**Slow Requests:**
```yaml
Alert: SlowRequests
Condition: p95_latency > 5  # 5 seconds
For: 5m
Severity: critical
Message: "API latency is {{ $value }}s"
```

## Troubleshooting

### Dashboard Shows "No Data"

**Check:**
1. Is Prometheus scraping metrics?
   ```bash
   kubectl get servicemonitor -n doc-intelligence
   ```

2. Are metrics being exposed?
   ```bash
   kubectl port-forward -n doc-intelligence svc/api-service 8000:8000
   curl http://localhost:8000/metrics
   ```

3. Is data source configured?
   - Grafana → Configuration → Data Sources
   - Test connection to Prometheus

### Queries Return Empty

**Debug:**
1. **Check if metric exists in Prometheus:**
   - Open Prometheus UI: http://localhost:9090
   - Query: `http_requests_total`
   - Should return data

2. **Verify label selectors:**
   ```promql
   # See all labels
   http_requests_total
   
   # Filter by label
   http_requests_total{endpoint="/health"}
   ```

3. **Check time range:**
   - Metrics might exist but outside current time window
   - Try "Last 24 hours" to see if any data exists

### Dashboard Not Loading

1. **Check ConfigMap:**
   ```bash
   kubectl get configmap -n monitoring | grep dashboard
   kubectl describe configmap grafana-dashboard-api-overview -n monitoring
   ```

2. **Verify Grafana is watching ConfigMaps:**
   ```bash
   kubectl logs -n monitoring deployment/prometheus-grafana | grep dashboard
   ```

3. **Restart Grafana:**
   ```bash
   kubectl rollout restart deployment/prometheus-grafana -n monitoring
   ```

## Next Steps

**For production:**
1. Set up alerts for critical metrics
2. Create notification channels (Slack, email)
3. Set up SSO/authentication
4. Configure data retention policies
5. Create dashboards for other services (extraction, evaluation)

**For learning:**
1. Explore pre-built dashboards (grafana.com/dashboards)
2. Learn more PromQL (prometheus.io/docs/prometheus/latest/querying/)
3. Try different visualization types
4. Create custom variables for filtering

## Resources

- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Basics](https://prometheus.io/docs/prometheus/latest/querying/basics/)
- [Dashboard Best Practices](https://grafana.com/docs/grafana/latest/best-practices/dashboard-best-practices/)
- [Pre-built Dashboards](https://grafana.com/grafana/dashboards/)

---

**You now have professional-grade monitoring dashboards!**

Grafana turns your Prometheus metrics into actionable insights, helping you understand your system's health at a glance.

