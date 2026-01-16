# Web Interface for Taxonomy Rationalization

This document describes the web interface for the Taxonomy Rationalization project.

## Overview

The web interface provides a user-friendly way to:
- Upload and ingest client taxonomies
- Generate LLM descriptions for categories
- Run hybrid matching between client and our taxonomies
- Review and manually adjust matches
- Export results
- Visualize our taxonomy structure

## Architecture

- **Backend**: FastAPI (Python) - `src/api/`
- **Frontend**: React + TypeScript + Material UI - `frontend/`
- **Database**: 
  - PostgreSQL with pgvector for embeddings
  - SQLite for job tracking

## Setup

### Prerequisites

1. PostgreSQL with pgvector extension running (see main README)
2. Environment variables configured (`.env` file)
3. Python dependencies installed (`uv sync`)
4. Node.js and npm installed

### Backend Setup

1. Install Python dependencies:
```bash
uv sync
```

2. Start the FastAPI server:
```bash
./run_api.sh
# Or manually:
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

### Frontend Setup

1. Install Node dependencies:
```bash
cd frontend
npm install
```

2. Create `.env` file (optional, defaults to `http://localhost:8000`):
```bash
VITE_API_URL=http://localhost:8000
```

3. Start the development server:
```bash
./run_frontend.sh
# Or manually:
cd frontend
npm run dev
```

The frontend will be available at `http://localhost:5173`

## Usage

### 1. Dashboard

View all uploaded taxonomies and their status:
- **uploaded**: File uploaded, ready for ingestion
- **ingesting**: Embeddings being generated
- **ingested**: Embeddings ready
- **augmenting**: LLM descriptions being generated
- **augmented**: Descriptions ready
- **matching**: Matching in progress
- **matched**: Matching complete
- **error**: Error occurred

### 2. Ingestion Page

**Step 1: Upload & Column Mapping**
1. Enter a Target ID (e.g., "zalando", "client_xyz")
2. Upload a CSV/Excel file
3. Map CSV columns to internal schema:
   - **L3 Column** (required): The most specific category level
   - **L2 Column** (optional): Mid-level category
   - **L1 Column** (optional): High-level category
   - **Definition Column** (optional): Category description

**Step 2: Ingest Embeddings**
- Generates embeddings for all taxonomy components (L1, L2, L3, full path, description)
- Stores in PostgreSQL vector database
- This step is required before matching

**Step 3: LLM Augmentation** (Optional)
- Generate descriptions for categories using LLM
- Customize prompt template (use `{l1}`, `{l2}`, `{l3}`, `{definition}` placeholders)
- Select LLM model (optional, uses default if not specified)

### 3. Matcher Page

**Configuration:**
- **Our Target ID**: Target ID for our internal taxonomy (e.g., "shq_hybrid")
- **Client Target ID**: Target ID for the client taxonomy to match
- **Confidence Threshold**: Minimum confidence for auto-accept (0.0 - 1.0)

**Matching:**
1. Click "Run Matching" to start hybrid matching
2. Review results in the table:
   - Green confidence chips: Above threshold (auto-accepted)
   - Yellow confidence chips: Below threshold (needs review)
3. Click any row to see top candidates and manually select a match
4. Use "Auto-Accept High Confidence" to accept all matches above threshold

**Status Indicators:**
- **auto**: Automatically matched (high confidence)
- **manual**: Manually selected match
- **review**: Needs manual review

### 4. Taxonomy Viewer

Visualize our internal taxonomy structure:
1. Enter Target ID (e.g., "shq_hybrid")
2. Click "Load Taxonomy"
3. Browse the hierarchical tree structure
4. Search for specific categories

### 5. Export

Export matched results:
- Available from the Dashboard (download icon)
- Exports as CSV or Excel format
- Includes all matched categories with confidence scores

## API Endpoints

### Upload
- `POST /upload` - Upload taxonomy CSV with column mapping

### Ingestion
- `POST /ingest` - Generate and store embeddings

### Augmentation
- `POST /augment` - Generate LLM descriptions

### Matching
- `POST /match` - Run hybrid matching

### Jobs
- `GET /jobs` - List all jobs
- `GET /jobs/{target_id}` - Get specific job

### Taxonomy
- `GET /our-taxonomy/{target_id}` - Get taxonomy tree

### Export
- `POST /export` - Export matched taxonomy

## Development

### Backend Structure
```
src/api/
├── main.py          # FastAPI app and routes
├── models.py        # Pydantic models
├── database.py      # SQLAlchemy models for job tracking
├── services.py     # Business logic
└── generate_descriptions_api.py  # LLM augmentation logic
```

### Frontend Structure
```
frontend/src/
├── api/
│   └── client.ts    # API client and types
├── components/
│   └── Layout.tsx   # Main layout with sidebar
└── pages/
    ├── Dashboard.tsx
    ├── Ingestion.tsx
    ├── Matcher.tsx
    └── TaxonomyViewer.tsx
```

## Troubleshooting

### Backend Issues
- Check PostgreSQL is running: `docker-compose ps`
- Verify environment variables in `.env`
- Check API logs for errors

### Frontend Issues
- Clear browser cache
- Check browser console for errors
- Verify API URL in `.env` file
- Ensure backend is running

### Database Issues
- Ensure embeddings are ingested before matching
- Check job status in Dashboard
- Review error messages in job details

## Next Steps

- Add user authentication
- Implement batch operations
- Add progress indicators for long-running operations
- Add export functionality to Matcher page
- Implement match history and versioning
