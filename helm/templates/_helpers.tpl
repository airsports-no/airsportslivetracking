{{/*
Expand the name of the chart.
*/}}
{{- define "live-tracking-chart.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "live-tracking-chart.fullname" -}}
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

{{- define "live_tracking.mysqlHost" }}
{{- printf "%s-mysql" .Release.Name }}
{{- end }}
{{- define "live_tracking.redisHost" }}
{{- printf "%s-redis-master" .Release.Name }}
{{- end }}
{{- define "live_tracking.traccarHost" }}
{{- printf "traccar-service" }}
{{- end }}


{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "live-tracking-chart.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "live-tracking-chart.labels" -}}
helm.sh/chart: {{ include "live-tracking-chart.chart" . }}
{{ include "live-tracking-chart.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "live-tracking-chart.selectorLabels" -}}
app.kubernetes.io/name: {{ include "live-tracking-chart.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "live-tracking-chart.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "live-tracking-chart.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
