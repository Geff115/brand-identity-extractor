# 🧠 Brand Identity Extractor API

The **Brand Identity Extractor** is a powerful API that extracts brand logos and color palettes from any website URL. It's built for developers and designers who need to capture brand assets automatically — perfect for mockups, presentations, and design automation.

---

## 🚀 Features

- **Logo Extraction** — Uses intelligent strategies to identify brand logos
- **Color Palette Detection** — Generates semantic palettes with role-based categorization
- **JavaScript Rendering** — Supports modern JS-heavy websites with headless browser tech
- **Caching** — Fast response times for repeat requests
- **Graceful Degradation** — Partial results returned when full extraction isn’t possible
- **Rate Limiting** — Prevents abuse with usage caps
- **Error Handling** — Clear and traceable error messages

---

## ⚙️ Getting Started

### Installation

Clone the repo and start the API with Docker:

```bash
git clone https://github.com/Geff115/brand-identity-extractor.git
cd brand-identity-extractor
cp .env.example .env
# Edit .env with your custom settings
docker-compose up -d
```

## Environment Variables

VARIABLE	        DESCRIPTION	                             DEFAULT
REDIS_URL	        Redis connection URL	                 redis://localhost:6379/0
OPENAI_API_KEY	    (Optional) OpenAI key for AI assist	     None
ADMIN_KEY	        Admin key for cache control	             admin-secret-key
RATE_LIMIT	        Max requests per hour	                 60
RATE_WINDOW	        Time window in seconds	                 3600

## 📬 API Endpoints
### 🔍 Extract Brand Identity

```http
POST /extract
```

Request:
```json
{
  "url": "https://example.com"
}
```

Headers (optional):

    - X-API-Key: Your API key

    - X-Rate-Limit-*: Rate limit info

    - X-Request-ID: Request trace ID

## ✅ Health Check

```http
GET /health
```
Returns system component status.

## 🧹 Clear Cache

```http
DELETE /cache
```
Headers:
    - X-Admin-Key: Admin key for authorization

Query param (alternative):
    - admin_key=your-admin-key

## 🔄 Response Format

Example response:
```json
{
  "url": "https://example.com",
  "logo": {
    "url": "https://example.com/logo.png",
    "image": "data:image/png;base64,...",
    "width": 200,
    "height": 100,
    "source": "meta-tag",
    "description": "Example company logo with blue text"
  },
  "colors": [
    {
      "hex": "#4285f4",
      "rgb": [66, 133, 244],
      "source": "logo-dominant"
    }
  ],
  "enhanced_colors": {
    "palette": {
      "primary": { "hex": "#4285f4", "name": "blue", ... },
      "secondary": { "hex": "#ea4335", "name": "red", ... },
      ...
    },
    "all_colors": {
      "logo": [...],
      "css": [...],
      "inline": []
    }
  },
  "success": true,
  "message": "Extraction completed successfully"
}
```

## 📉 Rate Limiting

Default: 60 requests/hour
Rate info is included in headers:
    - X-Rate-Limit-Limit
    - X-Rate-Limit-Remaining
    - X-Rate-Limit-Reset

Exceeding this limit returns 429 Too Many Requests.

## ❌ Error Handling

Consistent error response:
```json
{
  "error": {
    "message": "Error description",
    "category": "network",
    "timestamp": 1646838291.234,
    "trace_id": "uuid"
  }
}
```
Common Error Categories
- network

- external_service

- validation

- authentication

- authorization

- resource

- rate_limit

- server

## 📦 Technologies

- Backend: FastAPI, Uvicorn

- Scraping: Playwright, Beautiful Soup

- Color Analysis: ColorThief, Pillow

- AI (Optional): OpenAI API

- Caching & Performance: Redis, Circuit Breaker, Request Debouncing

- Testing: Pytest, HTTPX

- Containerization: Docker, Docker Compose

## 🛠️ Future Enhancements

- Font and tagline extraction

- Layout & brand guideline generation

- Logo vectorization

- GraphQL support

- Client SDKs

- CMS & design tool plugins (Figma, Sketch)

- Brand consistency and accessibility checks

## 📌 Examples

Extract Identity:
```bash
curl -X POST "https://api.example.com/extract" \
     -H "Content-Type: application/json" \
     -d '{"url": "https://www.spotify.com"}'
```

Health Check:
```bash
curl "https://api.example.com/health"
```

Clear Cache (Admin):
```bash
curl -X DELETE "https://api.example.com/cache" \
     -H "X-Admin-Key: your-admin-key"
```

## 📫 Contact & Support
For issues, suggestions, or contributions:
    - Email: gabrieleffangha2@gmail.com
    - GitHub: [https://github.com/Geff115/brand-identity-extractor](github.com/Geff115/brand-identity-extractor)