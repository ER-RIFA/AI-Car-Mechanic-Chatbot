# AI Car Mechanic Chatbot

An AI-powered car mechanic assistant that helps users describe vehicle problems, receive preliminary diagnostic guidance, upload vehicle media, and book a mechanic.

The application uses a **deterministic automotive diagnostic engine first**, with **selective Gemini fallback** for unsupported or ambiguous automotive cases and image analysis. This keeps common diagnostics predictable while limiting unnecessary AI API usage.

## Features

- Conversational vehicle diagnostics
- Automotive component and symptom detection
- Context-aware follow-up questions
- Deterministic rule-based diagnosis for common problems
- Selective Gemini AI fallback
- Image upload and AI-assisted image analysis
- Audio and video upload support
- Structured diagnosis records
- Mechanic booking flow
- REST API architecture
- File validation and size limits
- Safety-oriented responses for serious vehicle conditions

## Tech Stack

### Frontend
- React
- TypeScript
- Vite
- Tailwind CSS

### Backend
- Python
- Django
- Django REST Framework

### Database
- SQLite
- Django ORM

### AI
- Google Gemini API

### Development / Deployment
- Git / GitHub
- Vercel for frontend
- AWS EC2 for backend

## Architecture

```text
React + TypeScript Frontend
            |
            | REST API
            v
     Django / DRF Backend
            |
     +------+-------+----------------+
     |              |                |
     v              v                v
Diagnostic       Media            Booking
 Engine          Handling          Flow
     |
     +-- Normalization
     +-- Semantic Interpretation
     +-- Rule Matching
     +-- Follow-up State
     |
     +-- Selective Gemini Fallback
            |
            v
        Gemini API

     Django ORM
          |
          v
        SQLite
```

## Diagnostic Approach

The diagnostic engine follows a deterministic-first pipeline:

```text
User message
     |
     v
Text normalization
     |
     v
Semantic extraction
     |
     +-- Components
     +-- Complaints
     +-- Context
     |
     v
Diagnostic rule matching
     |
     +-- Matched
     +-- Needs information
     +-- Ambiguous
     +-- Unsupported
     |
     v
Structured response
```

The system supports common automotive scenarios including starting problems, clicking while starting, overheating, brake issues, warning lights, tire problems, battery warnings, oil leaks, steering vibration, exhaust smoke, and AC cooling problems.

The semantic layer also supports reusable component-oriented handling for areas such as lighting, horns, wipers, windows, doors, mirrors, tires, brakes, and other automotive components.

## Conversational Follow-ups

When the available information is insufficient, the diagnostic engine stores a pending follow-up state.

For example:

```text
User:
"My car horn doesn't work"

Assistant:
"What is happening with the horn system?"
```

The next user message is interpreted as an answer to the pending diagnostic question rather than being treated as an unrelated new conversation.

Follow-up information is accumulated in conversation state so the assistant can progressively narrow the problem instead of repeatedly asking the same question.

## Gemini Integration

Gemini is used selectively rather than for every message.

The intended decision flow is:

```text
User request
     |
     v
Deterministic diagnostic engine
     |
     +-- Confident match --------> Return diagnosis
     |
     +-- Needs information -----> Ask follow-up
     |
     +-- Non-automotive ---------> Clarify
     |
     +-- Unsupported automotive
                 |
                 v
            Gemini fallback
```

Gemini is also used for supported image-analysis scenarios.

Structured AI responses are validated before being used by the application. If AI processing fails or does not provide sufficient information, the application does not fabricate a diagnosis.

## Media Uploads

The application supports:

| Media | Formats |
|---|---|
| Images | JPEG, PNG, WEBP |
| Audio | MP3, WAV, OGG, WEBM |
| Video | MP4, MOV, WEBM |

The current maximum upload size is **10 MB**.

Uploads are validated using file extension, MIME type, file signature, and size checks before being stored.

Images can be sent to Gemini for automotive image analysis when appropriate.

Audio and video can be uploaded and associated with the conversation; the current implementation can request a text description when automated interpretation is not available.

## Mechanic Booking

After diagnosis, users can start a mechanic booking flow.

Booking information includes:

- Customer name
- Phone
- Email
- Vehicle make/model/year
- Preferred date/time
- Service address
- Booking status

The current booking implementation stores appointment information and supports pending, confirmed, and cancelled states. It does not implement a real mechanic availability or scheduling system.

## API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/chat/` | Process conversational diagnostic requests |
| POST | `/api/upload/` | Validate and upload media |
| POST | `/api/diagnosis/` | Create/retrieve structured diagnosis information |
| POST | `/api/booking/` | Create a mechanic booking |
| GET | `/api/booking/{id}/` | Retrieve booking information |

## Database Models

The backend uses Django ORM with SQLite.

Main entities:

- **Conversation** — chat/session information
- **Message** — user and assistant messages
- **MediaAttachment** — uploaded media metadata
- **Diagnosis** — symptoms, follow-up answers, result, service recommendation, and source
- **Booking** — customer, vehicle, appointment, and service information

## Project Structure

```text
AI-Car-Mechanic-Chatbot/
|
+-- backend/
|   +-- manage.py
|   +-- mechanic/
|       +-- diagnostic_engine/
|       |   +-- matcher.py
|       |   +-- normalizer.py
|       |   +-- rules.py
|       |   +-- semantics.py
|       |   +-- follow_up.py
|       |   +-- tests.py
|       |
|       +-- services/
|       |   +-- chat_service.py
|       |   +-- gemini_service.py
|       |
|       +-- models.py
|       +-- serializers.py
|       +-- views.py
|       +-- urls.py
|
+-- frontend/
|   +-- src/
|       +-- api/
|       +-- components/
|       +-- App.tsx
|       +-- main.tsx
|
+-- README.md
+-- PROJECT_DOCUMENTATION.md
```

## Local Setup

### Backend

```bash
cd backend
python -m venv .venv
```

Windows:

```powershell
.venv\Scriptsctivate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run migrations:

```bash
python manage.py migrate
```

Start Django:

```bash
python manage.py runserver
```

Backend:

```text
http://127.0.0.1:8000
```

### Frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Frontend:

```text
http://localhost:5173
```

## Environment Variables

### Backend

Create a local `.env` file:

```env
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

GEMINI_API_KEY=your-gemini-api-key
GEMINI_MODEL=gemini-2.0-flash
```

### Frontend

```env
VITE_API_BASE_URL=http://localhost:8000
VITE_MAX_UPLOAD_SIZE_MB=10
```

Never commit real API keys or secrets to GitHub.

## Testing

The project includes diagnostic engine and API-level tests covering:

- Common automotive symptoms
- Component classification
- Follow-up handling
- Ambiguous inputs
- Unsupported/non-automotive requests
- Media handling
- API responses
- Booking flow

Run backend tests with:

```bash
python manage.py test
```

## Design Decisions

### Deterministic First

Known automotive problems are handled using deterministic logic before invoking an external AI model.

This provides:

- Predictable common-case responses
- Lower unnecessary API usage
- Faster responses for known problems
- Easier debugging
- Better control over safety-related responses

### Selective AI

Gemini is used when deterministic logic cannot confidently handle an automotive request or when image analysis is appropriate.

### Django ORM + SQLite

SQLite is used for the current implementation through Django ORM. MongoDB is not required for this architecture.

The database layer can later be migrated to a production relational database such as PostgreSQL.

### REST API

The frontend and backend communicate through REST APIs, keeping the two layers independently deployable.

## Safety

The chatbot provides preliminary automotive guidance and is not a replacement for a qualified mechanic or physical vehicle inspection.

The diagnostic system includes safety-oriented guidance for potentially serious conditions such as severe overheating, suspected brake failure, fuel leaks, and severe tire damage.

## Current Limitations

- The deterministic knowledge base covers a defined set of common automotive problems.
- Gemini functionality depends on API availability and configuration.
- Audio and video uploads do not currently provide complete automated diagnostic interpretation.
- Booking does not connect to a real mechanic scheduling or availability system.
- Local media storage is used in the current implementation.
- SQLite is suitable for the current project but a production deployment could use PostgreSQL.
- User authentication is not currently implemented.

## Future Improvements

- PostgreSQL for production
- S3/object storage for media
- Real mechanic availability and scheduling
- User authentication and vehicle profiles
- Speech-to-text for audio
- Automated video analysis
- Expanded automotive diagnostic knowledge base
- Mechanic dashboard
- Booking notifications
- Maintenance reminders
- Production monitoring and analytics

## Disclaimer

This application provides preliminary diagnostic assistance based on user-provided information. It does not replace professional automotive inspection, repair advice, or emergency assistance.
