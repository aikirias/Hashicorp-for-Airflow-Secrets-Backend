{{- with secret "database/creds/airflow-dynamic-read" -}}
{
  "username": "{{ .Data.username }}",
  "password": "{{ .Data.password }}",
  "lease_id": "{{ .LeaseID }}",
  "lease_duration": {{ .LeaseDuration }}
}
{{- end -}}
