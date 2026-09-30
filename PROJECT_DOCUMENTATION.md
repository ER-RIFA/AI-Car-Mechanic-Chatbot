# AI Car Mechanic Chatbot
## Technical Project Documentation

## 1. Introduction

The AI Car Mechanic Chatbot is a full-stack web application that provides conversational assistance for common vehicle problems.

A user can describe a vehicle issue in natural language, answer follow-up questions, upload supporting media, view diagnostic information, and proceed to a mechanic booking flow.

The system combines deterministic automotive diagnostic logic with selective Gemini AI integration.

The central architectural principle is:

> Use deterministic logic whenever the problem can be handled reliably, and use generative AI only when additional reasoning or media analysis is appropriate.

## 2. Objectives

1. Provide a conversational interface for vehicle problems.
2. Identify automotive components and complaints from natural-language input.
3. Diagnose common vehicle problems using deterministic rules.
4. Ask contextual follow-up questions when information is insufficient.
5. Use Gemini selectively for unsupported or complex automotive cases.
6. Support vehicle-related image, audio, and video uploads.
7. Provide structured diagnosis information.
8. Allow users to submit a mechanic booking request.
9. Minimize unnecessary external AI API usage.

## 3. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite |
| Styling | Tailwind CSS |
| Backend | Python, Django |
| API | Django REST Framework |
| Database | SQLite |
| ORM | Django ORM |
| AI | Google Gemini API |
| Version Control | Git / GitHub |
| Intended Frontend Hosting | Vercel |
| Intended Backend Hosting | AWS EC2 |

## 4. High-Level Architecture

```text
                    +----------------------+
                    |    React Frontend    |
                    | TypeScript + Vite    |
                    +----------+-----------+
                               |
                               | REST
                               v
                    +----------------------+
                    |    Django / DRF      |
                    |       Backend        |
                    +----------+-----------+
                               |
          +--------------------+--------------------+
          |                    |                    |
          v                    v                    v
+----------------+    +----------------+    +----------------+
| Diagnostic     |    | Media Handling |    | Booking        |
| Engine         |    |                |    | Service        |
+-------+--------+    +-------+--------+    +----------------+
        |                     |
        |                     v
        |              +-------------+
        |              |   Gemini    |
        |              | Image/AI    |
        |              +-------------+
        |
        v
+----------------+
| Django ORM     |
| SQLite         |
+----------------+
```

## 5. Request Processing

```text
User message
     |
     v
Conversation lookup/creation
     |
     v
Text normalization
     |
     v
Semantic extraction
     |
     +---- Known problem ---------> Structured diagnosis
     |
     +---- Missing information ---> Follow-up question
     |
     +---- Ambiguous -------------> Clarification / AI fallback
     |
     +---- Unsupported automotive -> Gemini fallback
     |
     +---- Non-automotive ---------> Clarification
```

## 6. Diagnostic Engine

The diagnostic engine is implemented under:

```text
backend/mechanic/diagnostic_engine/
```

Important modules include:

```text
normalizer.py
rules.py
semantics.py
follow_up.py
matcher.py
tests.py
```

### Normalization

User messages are normalized to make the diagnostic process less dependent on exact wording.

The normalization layer handles common variations such as:

- Case
- Automotive synonyms
- Common contractions
- Singular/plural terminology
- Common spelling variations

### Semantic Extraction

The semantic layer extracts reusable concepts from the user's message.

The main concepts include:

- Automotive components
- Complaints
- Contextual evidence

Examples of components include:

- Engine
- Brakes
- Tires
- Battery
- Steering
- Horn
- Lighting
- Wipers
- Windows
- Doors
- Mirrors

Examples of complaints include:

- Not working
- Noise
- Vibration
- Leakage
- Overheating
- Warning
- Smoke
- Performance problems

## 7. Rule-Based Diagnosis

Known problems are represented using diagnostic rules.

The current rule set covers common scenarios such as:

- Vehicle not starting
- Clicking while starting
- Engine overheating
- Brake squealing/grinding or related brake problems
- Check-engine warning
- Pulling or vibration while braking
- Flat/low-pressure tire
- Battery warning or dim lights
- Oil leak
- Steering vibration
- Exhaust smoke
- AC not cooling

The matcher uses available semantic evidence to determine whether a rule has sufficient support.

The result can be:

- Matched
- Needs information
- Ambiguous
- Unsupported

## 8. Conversational Follow-up State

A diagnostic problem often cannot be resolved from one sentence.

For this reason, the engine maintains follow-up state.

Example:

```text
User:
"My car horn doesn't work."

        |
        v

Component:
horn

        |
        v

More information required

        |
        v

Assistant:
"What is happening with the horn system?"
```

The user's next response is interpreted in the context of the pending question.

This prevents the engine from treating every response as an unrelated new problem.

The follow-up mechanism stores relevant information and can transition to another question when the previous question has been answered.

## 9. Generic Component Follow-up

The component follow-up mechanism is designed to be reusable.

The component is stored as data rather than embedding a separate hard-coded conversation flow for each component.

Conceptually:

```text
component = horn
component = lighting
component = wiper
component = window
component = door
...
```

A component-specific clarification can therefore be generated using the same state mechanism.

This design is intended to make it easier to extend the system to additional automotive components.

## 10. Gemini Fallback

Gemini is not called for every user message.

The preferred processing order is:

```text
Deterministic classification
        |
        +---- Match ---------> Use deterministic result
        |
        +---- Follow-up -----> Ask user
        |
        +---- Ambiguous -----> Handle clarification / fallback
        |
        +---- Unsupported
                    |
                    v
                 Gemini
```

This design reduces unnecessary API calls and keeps common diagnostics deterministic.

Gemini responses are processed through application-level validation before being used.

If Gemini cannot provide a usable result, the application returns a controlled clarification rather than inventing a diagnosis.

## 11. Image Analysis

Image uploads can be processed through the Gemini integration when an automotive visual interpretation is appropriate.

The process is:

```text
Image
  |
  v
Upload validation
  |
  v
Media attachment
  |
  v
Automotive relevance
  |
  v
Gemini image analysis
  |
  v
Structured assistant response
```

If analysis is unavailable or inconclusive, the assistant requests additional information.

## 12. Audio and Video

The backend accepts audio and video files.

The current implementation validates and stores these uploads and associates them with the relevant conversation.

Complete automated audio/video diagnostic interpretation is outside the current implementation.

Where direct analysis is unavailable, the assistant can ask the user to describe the observed symptom in text.

## 13. Media Validation

Media uploads are protected by multiple validation checks.

The application checks:

- File extension
- MIME type
- File signature
- Maximum size

Maximum upload size:

```text
10 MB
```

Supported formats:

```text
Images:
JPEG
PNG
WEBP

Audio:
MP3
WAV
OGG
WEBM

Video:
MP4
MOV
WEBM
```

Generated filenames are used for uploaded files rather than relying directly on user-provided names.

## 14. Database Design

The application uses Django ORM with SQLite.

### Conversation
Represents a user's diagnostic conversation/session.

### Message
Stores user and assistant messages.

### MediaAttachment
Stores metadata associated with uploaded media.

### Diagnosis
Stores:
- Symptoms
- Follow-up answers
- Diagnostic result
- Recommended service
- Diagnostic source

### Booking
Stores:
- Customer details
- Vehicle details
- Preferred appointment information
- Service address
- Booking status

Relationship overview:

```text
Conversation
   |
   +-- Message
   |
   +-- MediaAttachment
   |
   +-- Diagnosis
           |
           +-- Booking
```

## 15. API Layer

### `POST /api/chat/`

Processes conversational diagnostic requests.

Responsibilities include:

- Conversation handling
- Message persistence
- Diagnostic processing
- Follow-up state
- Gemini fallback when appropriate

### `POST /api/upload/`

Handles media uploads.

Responsibilities include:

- File validation
- Media storage
- Conversation association
- Supported media processing

### `POST /api/diagnosis/`

Handles structured diagnosis operations.

### `POST /api/booking/`

Creates a mechanic booking.

### `GET /api/booking/{id}/`

Retrieves booking information.

## 16. Booking Architecture

```text
Diagnostic Result
       |
       v
Book Mechanic
       |
       v
Customer Details
       |
       v
Vehicle Details
       |
       v
Preferred Date / Time
       |
       v
Service Address
       |
       v
Booking Created
```

Booking statuses:

```text
pending
confirmed
cancelled
```

The implementation does not currently connect to a live mechanic availability or calendar system.

## 17. Safety Handling

Some automotive problems can represent immediate safety concerns.

The diagnostic engine includes safety-oriented guidance for scenarios such as:

- Severe overheating
- Suspected brake failure
- Fuel leaks
- Severe tire damage

The chatbot provides preliminary information only.

It does not replace a qualified mechanic or physical vehicle inspection.

## 18. Error Handling

The backend validates input before processing it.

The application handles conditions including:

- Missing request data
- Invalid media files
- Oversized uploads
- Invalid booking information
- Unsupported diagnostic requests
- Insufficient information
- Gemini failures

A failed AI request should result in a controlled response rather than an invented diagnostic conclusion.

## 19. Security

Secrets are supplied through environment variables.

Example:

```env
GEMINI_API_KEY=your-key
```

Real API keys must not be committed to GitHub.

The `.env` file is intended to remain outside source control.

## 20. Local Development

### Backend

```powershell
cd backend
.venv\Scriptsctivate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Default development addresses:

```text
Backend:
http://127.0.0.1:8000

Frontend:
http://localhost:5173
```

## 21. Testing

The project contains diagnostic and API tests covering areas including:

- Automotive symptom matching
- Component classification
- Follow-up state
- Ambiguous input
- Unsupported/non-automotive input
- Media behavior
- API responses
- Booking behavior

Backend tests can be executed using:

```bash
python manage.py test
```

## 22. Deployment Design

The intended deployment arrangement is:

```text
                User
                 |
                 v
        Vercel / React App
                 |
                 | HTTPS REST
                 v
            AWS EC2
                 |
          Django / DRF
                 |
       +---------+---------+
       |                   |
       v                   v
 Diagnostic Engine      Gemini API
       |
       v
     SQLite
```

For a larger production environment, the database and media layers can be migrated to managed infrastructure.

## 23. Architectural Decisions

### Why deterministic diagnosis?

A rule-based engine provides predictable behavior for known automotive problems and avoids unnecessary AI calls.

### Why selective Gemini?

Generative AI is useful for ambiguous, unsupported automotive inputs and image analysis, but using it for every request increases cost and makes behavior less predictable.

### Why Django ORM + SQLite?

Django ORM provides a clean data model and keeps the application independent of database-specific query logic. SQLite is sufficient for the current assignment and can later be replaced with PostgreSQL.

### Why REST?

REST keeps the React frontend and Django backend independently deployable and provides a simple interface between the two layers.

## 24. Limitations

Current limitations include:

1. The deterministic diagnostic engine covers a defined set of common problems rather than every possible vehicle issue.
2. Gemini requires a valid API configuration.
3. Audio and video are supported as uploads but do not currently provide complete automated diagnosis.
4. Booking does not use real mechanic availability.
5. Local media storage is used in the current setup.
6. SQLite is intended for the current project rather than high-scale production use.
7. Authentication and user accounts are not currently implemented.

## 25. Future Scope

Potential future enhancements include:

- PostgreSQL
- S3/object storage
- User authentication
- Vehicle profiles
- Service history
- Speech-to-text
- Video analysis
- Expanded diagnostic knowledge base
- Real mechanic scheduling
- Booking notifications
- Mechanic dashboard
- Maintenance reminders
- Monitoring and analytics

## 26. Conclusion

The project demonstrates a full-stack approach to AI-assisted automotive diagnostics.

Its architecture combines deterministic software logic with selective generative AI, allowing common vehicle problems to be handled predictably while retaining an AI fallback for cases requiring additional interpretation.

The system also demonstrates conversational state management, media handling, structured persistence, REST API design, and a basic mechanic booking workflow.
