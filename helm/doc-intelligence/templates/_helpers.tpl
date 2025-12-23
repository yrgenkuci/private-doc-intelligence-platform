{{/*
Expand the name of the chart.
*/}}
{{- define "doc-intelligence.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "doc-intelligence.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "doc-intelligence.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "doc-intelligence.labels" -}}
helm.sh/chart: {{ include "doc-intelligence.chart" . }}
{{ include "doc-intelligence.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "doc-intelligence.selectorLabels" -}}
app.kubernetes.io/name: {{ include "doc-intelligence.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
API selector labels
*/}}
{{- define "doc-intelligence.api.selectorLabels" -}}
{{ include "doc-intelligence.selectorLabels" . }}
app.kubernetes.io/component: api
{{- end }}

{{/*
Worker selector labels
*/}}
{{- define "doc-intelligence.worker.selectorLabels" -}}
{{ include "doc-intelligence.selectorLabels" . }}
app.kubernetes.io/component: worker
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "doc-intelligence.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "doc-intelligence.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{/*
Get the image tag
*/}}
{{- define "doc-intelligence.imageTag" -}}
{{- .Values.api.image.tag | default .Chart.AppVersion }}
{{- end }}

{{/*
Redis host
*/}}
{{- define "doc-intelligence.redisHost" -}}
{{- if .Values.redis.enabled }}
{{- printf "%s-redis-master" .Release.Name }}
{{- else }}
{{- .Values.config.redis.host | default "redis" }}
{{- end }}
{{- end }}

{{/*
MinIO host
*/}}
{{- define "doc-intelligence.minioHost" -}}
{{- if .Values.minio.enabled }}
{{- printf "%s-minio" .Release.Name }}
{{- else }}
{{- .Values.config.storage.host | default "minio" }}
{{- end }}
{{- end }}

