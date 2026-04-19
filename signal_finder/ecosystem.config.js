module.exports = {
  apps: [{
    name: "signal-finder",
    script: "main.py",
    interpreter: "python",
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: "1G",
    log_date_format: "YYYY-MM-DD HH:mm Z",
    error_file: "logs/error.log",
    out_file: "logs/out.log",
    merge_logs: true,
    env: {
      PYTHONUNBUFFERED: "1"
    }
  }]
}
