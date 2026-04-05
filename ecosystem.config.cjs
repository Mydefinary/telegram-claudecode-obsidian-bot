module.exports = {
  apps: [
    {
      name: "telegram-obsidian-bot",
      script: "bot.py",
      interpreter: "python",
      cwd: "C:/개발/telegram-obsidian-bot",
      watch: false,
      autorestart: true,
      max_restarts: 10,
      restart_delay: 5000,
      log_date_format: "YYYY-MM-DD HH:mm:ss",
      error_file: "logs/pm2-error.log",
      out_file: "logs/pm2-out.log",
      merge_logs: true,
    },
  ],
};
