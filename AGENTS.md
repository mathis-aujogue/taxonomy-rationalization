# Taxonomy Rationalization - Agent Documentation

## Overview

This project matches categories from a client taxonomy (`their_taxonomy.csv`) to our internal taxonomy (`our_taxonomy.csv`) using three different approaches:

1. **Embeddings-based matching**: Uses semantic similarity via Azure OpenAI embeddings and pgvector
2. **LLM-based matching**: Uses Azure OpenAI LLM to directly match categories
3. **Hybrid matching**: Combines embeddings (fast filtering) with LLM (accurate selection)

## Package Manager

This project uses **uv** as the package manager. All scripts should be run with:

```bash
uv run src/embeddings_matcher.py
uv run src/llm_matcher.py
uv run src/hybrid_matcher.py
```

### Installing Dependencies

```bash
# Install all dependencies from pyproject.toml
uv sync

# Add a new dependency
uv add package-name

# Add a development dependency
uv add --dev package-name
```

## Database Setup (pgvector with Docker Compose)

The project uses PostgreSQL with the pgvector extension for vector similarity search.

### Starting the Database

```bash
# Start PostgreSQL with pgvector in the background
docker-compose up -d

# Check if it's running
docker-compose ps

# View logs
docker-compose logs -f postgres

# Stop the database
docker-compose down

# Stop and remove volumes (clean slate)
docker-compose down -v
```

### Database Connection

The connection string is configured via environment variables:
- `LOCAL_POSTGRESQL_URL` - Connection string for local PostgreSQL
- Format: `postgresql://user:password@localhost:5432/dbname`

The `DB_TYPE` environment variable should be set to `"local"` for local development.

## Environment Variables

Create a `.env` file in the project root with the following variables:

```bash
# Azure OpenAI Configuration
AZURE_EMBEDDING_API_KEY=your_embedding_api_key
AZURE_CHAT_API_KEY=your_chat_api_key
AZURE_API_VERSION=2024-02-15-preview
AZURE_EMBEDDING_ENDPOINT=https://your-resource.openai.azure.com
AZURE_CHAT_ENDPOINT=https://your-resource.openai.azure.com
AZURE_EMBEDDING_MODEL=text-embedding-ada-002
AZURE_CHAT_MODEL=gpt-5.1

# PostgreSQL Configuration
DB_TYPE=local
LOCAL_POSTGRESQL_URL=postgresql://postgres:postgres@localhost:5433/taxonomy_db
```

See `.env.example` for a complete template.

## Inputs

### 1. `assets/their_taxonomy.csv` (Client Taxonomy)

**Structure:**
- `DATA_SOURCE`: Source identifier (e.g., "ZALANDO")
- `COMMODITY_L1`: Top-level category
- `COMMODITY_L2`: Second-level category
- `COMMODITY_L3`: Third-level category (to be matched)
- `GDW_SUBCATEGORY`: Target column (currently 0, will be filled with matched category)
- `SUM(AMOUNT)`: Spending amount (for reference)

**Example:**
```csv
DATA_SOURCE,COMMODITY_L1,COMMODITY_L2,COMMODITY_L3,GDW_SUBCATEGORY,SUM(AMOUNT)
ZALANDO,(Corporate) Property,Facility Management,Canteen Services,0,11627710.1751421
```

### 2. `assets/our_taxonomy.csv` (Our Taxonomy)

**Structure:**
- `CATEGORY L2`: Second-level category
- `CATEGORY L3`: Third-level category (target for matching)
- `DEFINITION`: Description of the category

**Example:**
```csv
,CATEGORY L2,CATEGORY L3,DEFINITION
BANKING SERVICES,BANKING SERVICES,APPRAISALS,Companies through which mortgage lenders order real estate valuation services...
```

## Outputs

### 1. Updated Original CSV

**File:** `assets/their_taxonomy.csv` (updated in-place with backup)

The `GDW_SUBCATEGORY` column is populated with the matched `CATEGORY L3` from our taxonomy.

**Format:**
```csv
DATA_SOURCE,COMMODITY_L1,COMMODITY_L2,COMMODITY_L3,GDW_SUBCATEGORY,SUM(AMOUNT)
ZALANDO,(Corporate) Property,Facility Management,Canteen Services,FOOD SERVICES,11627710.1751421
```

### 2. Detailed Report CSV

**File:** `results/{method}_detailed_report_{timestamp}.csv`

Contains comprehensive matching information:

**Columns:**
- `their_category_l1`: Original L1 category
- `their_category_l2`: Original L2 category
- `their_category_l3`: Original L3 category (to match)
- `matched_category_l2`: Matched L2 from our taxonomy
- `matched_category_l3`: Matched L3 from our taxonomy
- `confidence_score`: Match confidence (0.0-1.0)
- `method_used`: Which matching method was used
- `top_3_candidates`: JSON array of top 3 candidates with scores
- `reasoning`: LLM reasoning (if available)

### 3. Summary Statistics

**File:** `results/{method}_summary_{timestamp}.json`

Contains aggregate statistics:

```json
{
  "total_categories": 213,
  "matched_categories": 195,
  "unmatched_categories": 18,
  "average_confidence": 0.87,
  "median_confidence": 0.89,
  "confidence_distribution": {
    "high (>0.8)": 150,
    "medium (0.6-0.8)": 35,
    "low (<0.6)": 10
  },
  "method": "hybrid",
  "execution_time_seconds": 245.3
}
```

## Ingesting Taxonomy Embeddings

Before running the embeddings or hybrid matchers, you need to ingest taxonomies into the vector database.

### Ingest Our Taxonomy

Ingest our taxonomy (only needs to be done once, or when our taxonomy changes):

```bash
uv run src/ingest_taxonomy.py --input-csv assets/our_taxonomy.csv
```

**Process:**
1. Loads our taxonomy from specified CSV file
2. Creates embeddings for each category using Azure OpenAI
3. Stores embeddings in the pgvector database with `taxonomy_type='our'` metadata
4. Shows progress bar during ingestion

**Options:**
- `--input-csv`: Path to our taxonomy CSV file (required)
- `--clear`: Flag to clear existing embeddings (requires manual table drop if needed)

**Performance:** ~2-3 minutes for 400+ categories

### Ingest Client Taxonomy

Ingest a client taxonomy (once per client):

```bash
uv run src/ingest_taxonomy.py --input-csv assets/client_taxonomy.csv --target-id zalando
```

**Process:**
1. Loads client taxonomy from specified CSV file
2. Creates embeddings for each L3 category
3. Stores embeddings in the pgvector database with `taxonomy_type='client'` and `target_id` metadata
4. Shows progress bar during ingestion

**Options:**
- `--input-csv`: Path to client taxonomy CSV file (required)
- `--target-id`: Target identifier for metadata (required for client taxonomies)

**Note:** If `--target-id` is provided, the script treats it as a client taxonomy. If not provided, it treats it as our taxonomy.

**Performance:** ~1-2 minutes for 200+ categories

**Note:** The embeddings matcher and hybrid matcher assume our taxonomy embeddings are already in the database. Ingest our taxonomy first before using those matchers.

### List Vector Database Contents

Inspect what's stored in the vector database:

```bash
uv run src/list_vector_db.py
```

**Output:**
- Total records count
- Breakdown by taxonomy type (our vs client)
- Breakdown by target_id (for client taxonomies)
- Count of embeddings per taxonomy type and target_id
- Sample records with metadata

**Use cases:**
- Verify ingestion was successful
- Check which client taxonomies are stored
- Inspect metadata structure
- Debug database contents

## Running the Matchers

### Embeddings Matcher

```bash
uv run src/embeddings_matcher.py
```

**Process:**
1. Loads both taxonomies
2. Assumes embeddings are already in the database (run `ingest_taxonomy.py` first)
3. For each client category, finds top-k similar matches using vector search
4. Selects best match above confidence threshold
5. Generates outputs

**Performance:** Fast (~2-5 minutes for 200+ categories)

**Prerequisites:** Run `uv run src/ingest_taxonomy.py` first

### LLM Matcher

```bash
uv run src/llm_matcher.py
```

**Process:**
1. Loads both taxonomies
2. For each client category:
   - Builds prompt with category hierarchy and our taxonomy
   - Calls Azure OpenAI LLM for matching
   - Parses structured response
3. Generates outputs

**Performance:** Slower (~10-20 minutes for 200+ categories, depends on rate limits)

### Hybrid Matcher

```bash
uv run src/hybrid_matcher.py
```

**Process:**
1. Assumes embeddings are already in the database (run `ingest_taxonomy.py` first)
2. Uses embeddings to get top-k candidates (fast filtering)
3. Uses LLM to select best match from candidates (accurate selection)
4. Combines confidence scores
5. Generates outputs

**Performance:** Balanced (~5-10 minutes for 200+ categories)

**Prerequisites:** Run `uv run src/ingest_taxonomy.py` first

## Testing

### Unit Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_embeddings_matcher.py

# Run with coverage
uv run pytest --cov=src --cov-report=html
```

### Test Data

Create test fixtures in `tests/fixtures/`:
- `test_their_taxonomy.csv` - Small subset of client taxonomy
- `test_our_taxonomy.csv` - Small subset of our taxonomy

### Manual Testing

1. **Test embeddings matcher:**
   ```bash
   uv run src/embeddings_matcher.py
   # Check results/embeddings_detailed_report_*.csv
   ```

2. **Test LLM matcher:**
   ```bash
   uv run src/llm_matcher.py
   # Check results/llm_detailed_report_*.csv
   ```

3. **Test hybrid matcher:**
   ```bash
   uv run src/hybrid_matcher.py
   # Check results/hybrid_detailed_report_*.csv
   ```

## Benchmarking

### Performance Benchmarks

Run the benchmark script to compare all three methods:

```bash
uv run src/benchmark.py
```

**Metrics tracked:**
- Execution time (total and per-category)
- API call count and cost estimation
- Match accuracy (requires ground truth)
- Confidence score distribution
- Memory usage

**Output:** `results/benchmark_report_{timestamp}.json`

### Accuracy Benchmarks

To measure accuracy, you need a ground truth dataset:

1. Create `assets/ground_truth.csv` with manual matches:
   ```csv
   their_category_l3,correct_category_l3
   Canteen Services,FOOD SERVICES
   Cleaning Services and goods,JANITORIAL SERVICES
   ```

2. Run accuracy evaluation:
   ```bash
   uv run src/evaluate_accuracy.py --ground-truth assets/ground_truth.csv
   ```

**Metrics:**
- Precision: Correct matches / Total matches
- Recall: Correct matches / Total possible matches
- F1 Score: Harmonic mean of precision and recall
- Top-k accuracy: Correct match in top-k candidates

### Cost Estimation

Estimate API costs for each method:

```bash
uv run src/estimate_costs.py
```

**Output:**
```
Method: embeddings
- Embedding API calls: 465 (our taxonomy) + 213 (their taxonomy) = 678
- Estimated cost: $0.013 (at $0.0001 per 1K tokens)

Method: llm
- LLM API calls: 213
- Estimated cost: $2.13 (at $0.01 per 1K tokens)

Method: hybrid
- Embedding API calls: 678
- LLM API calls: 213
- Estimated cost: $2.14
```

## Project Structure

```
taxonomy-rationalization/
├── .env.example                 # Environment variable template
├── docker-compose.yml           # PostgreSQL with pgvector setup
├── pyproject.toml               # Project dependencies (uv)
├── AGENTS.md                    # This file
├── assets/
│   ├── our_taxonomy.csv        # Our taxonomy (input)
│   └── their_taxonomy.csv      # Client taxonomy (input/output)
├── src/
│   ├── services.py             # Services initialization
│   ├── models.py               # Pydantic models
│   ├── ingest_taxonomy.py      # Unified ingestion script (our or client taxonomy)
│   ├── list_vector_db.py       # List vector database contents
│   ├── embeddings_matcher.py   # Embeddings-based matching
│   ├── llm_matcher.py          # LLM-based matching
│   ├── hybrid_matcher.py       # Hybrid matching
│   ├── benchmark.py            # Performance benchmarking
│   ├── evaluate_accuracy.py    # Accuracy evaluation
│   ├── estimate_costs.py      # Cost estimation
│   ├── utils/
│   │   ├── constants.py        # Environment variables
│   │   ├── data_loader.py      # CSV loading utilities
│   │   ├── threshold_detection.py  # Auto threshold detection
│   │   └── progress.py         # Progress tracking
│   └── output_handler.py       # Output generation
├── results/                     # Generated outputs (gitignored)
└── tests/                       # Test files
```

## Troubleshooting

### Database Connection Issues

```bash
# Check if PostgreSQL is running
docker-compose ps

# Check connection string format
echo $LOCAL_POSTGRESQL_URL

# Test connection manually (explicitly specifying port 5433)
docker-compose exec postgres psql -U postgres -d taxonomy_db -h localhost -c "SELECT 1;"
```
# Or, using psql outside the container with the correct port:
# psql -h localhost -U postgres -d taxonomy_db -p 5433 -c "SELECT 1;"

### Azure OpenAI Issues

- Verify API keys are set correctly in `.env`
- Check endpoint URLs (should end with `/openai/deployments/...`)
- Verify deployment names match your Azure OpenAI resource
- Check rate limits if getting 429 errors

### Vector Store Issues

```bash
# Check if pgvector extension is installed
docker-compose exec postgres psql -U postgres -d taxonomy_db -c "CREATE EXTENSION IF NOT EXISTS vector;"

# Check if table exists
docker-compose exec postgres psql -U postgres -d taxonomy_db -c "\dt"
```

## Next Steps

1. Set up environment variables in `.env`
2. Start PostgreSQL: `docker-compose up -d`
3. Ingest our taxonomy: `uv run src/ingest_taxonomy.py --input-csv assets/our_taxonomy.csv` (required for embeddings/hybrid matchers)
4. (Optional) Ingest client taxonomy: `uv run src/ingest_taxonomy.py --input-csv assets/client_taxonomy.csv --target-id zalando`
5. Run unified matcher: `uv run src/match_taxonomies.py --input-csv assets/their_taxonomy.csv --strategy all`
6. Review results in `results/` directory
7. Compare methods and use best one for production matching
