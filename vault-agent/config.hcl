exit_after_auth = false
pid_file = "/vault-agent/agent.pid"

auto_auth {
  method "approle" {
    config = {
      role_id_file_path   = "/vault-agent/approle/role_id"
      secret_id_file_path = "/vault-agent/approle/secret_id"
    }
  }
  sink "file" {
    config = {
      path = "/vault-agent/output/agent-token"
      mode = 0644
    }
  }
}

template {
  source      = "/vault-agent/templates/db-creds.tpl"
  destination = "/vault-agent/output/db-creds.json"
  command     = "/vault-agent/scripts/sync_dynamic_creds.sh /vault-agent/output/db-creds.json"
}
