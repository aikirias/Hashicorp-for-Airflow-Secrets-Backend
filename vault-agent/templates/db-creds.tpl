{{- with secret "database/creds/airflow-dynamic-read" -}}
{
  "username": "{{ .Data.username }}",
  "password": "{{ .Data.password }}",
  "lease_id": "{{ .LeaseID }}",
  "lease_duration": {{ .LeaseDuration }},
  "conn_uri": "postgresql://{{ .Data.username }}:{{ .Data.password }}@demo-db:5432/demo"
}
{{- end -}}
