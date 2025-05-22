# dl-api & Telegram Bot

A FastAPI-based microservice and Telegram bot for downloading videos from whitelisted platforms (YouTube, Facebook, Instagram, TikTok, etc) via group chat commands.

## Features
- Download videos from YouTube, Facebook, Instagram, TikTok, and more (configurable whitelist)
- Telegram bot responds only in allowed groups
- API key protected FastAPI backend
- Dockerized for easy deployment
- Configurable via environment variables

## Quick Start (Docker Compose)

1. **Clone the repository:**
   ```sh
   git clone https://github.com/tarkant/dl-api.git
   cd dl-api
   ```

2. **Edit `docker-compose.yml`:**
   - Set your own `API_KEY`, `TELEGRAM_TOKEN`, and allowed group IDs.
   - Optionally adjust the URL whitelist.

3. **Build and run:**
   ```sh
   docker compose up --build -d
   ```

4. **Add your bot to your Telegram group(s).**
   - Make sure the group ID is in `ALLOWED_GROUP_IDS`.
   - [How to get your group ID?](https://stackoverflow.com/a/32572159)

5. **Send a supported video URL in the group.**
   - The bot will download and send the video if the URL is whitelisted.

## Environment Variables

| Variable                | Description                                                      |
|------------------------ |------------------------------------------------------------------|
| `API_KEY`               | Secret key for API authentication (required)                     |
| `TELEGRAM_TOKEN`        | Telegram bot token (required)                                     |
| `API_BASE_URL`          | URL for the FastAPI backend (default: http://dl-api:8000)    |
| `ALLOWED_GROUP_IDS`     | JSON array or comma-separated list of allowed group IDs           |
| `ALLOWED_URL_WHITELIST` | JSON array or comma-separated list of allowed URL prefixes        |
| `LOG_VERBOSE`           | Set to `1` for verbose logs, `0` for minimal logs                |

## Example `docker-compose.yml`

```yaml
version: '3.8'
services:
  dl-api:
    build: .
    container_name: dl-api
    environment:
      - API_KEY=changeme
    ports:
      - "8000:8000"
    restart: unless-stopped
    command: uvicorn main:app --host 0.0.0.0 --port 8000
    networks:
      - yt-dlp-net

  telegram-bot:
    build: .
    container_name: telegram-bot
    environment:
      - API_KEY=changeme
      - TELEGRAM_TOKEN=your_telegram_token
      - API_BASE_URL=http://dl-api:8000
      - ALLOWED_GROUP_IDS=[-1001234567890]
      - ALLOWED_URL_WHITELIST=["https://www.youtube.com/","https://youtu.be/","https://music.youtube.com/","https://www.facebook.com/","https://fb.watch/","https://www.instagram.com/","https://www.tiktok.com/"]
      - LOG_VERBOSE=1
    depends_on:
      - dl-api
    restart: unless-stopped
    command: python telegram_bot.py
    networks:
      - yt-dlp-net

networks:
  yt-dlp-net:
    driver: bridge
```

## Security
- **Never commit your real API keys or Telegram tokens.**
- Use environment variables or Docker secrets for sensitive data.

## License
MIT
