# Historical Matching Workflow Guide

Complete guide for ingesting historical mappings, running matches, and comparing results.

## Prerequisites

1. **Database running**: Ensure PostgreSQL with pgvector is running
   ```bash
   docker-compose up -d
   ```

2. **Environment variables**: Ensure `.env` file is configured with Azure OpenAI credentials

## Step 1: Ingest Historical Mappings

Ingest the historical mapping CSV into the vector database. The client L2+L3 categories will be embedded, and the matched_l2+matched_l3 will be stored in metadata.

### Basic Usage

```bash
uv run src/ingest_historical_mapping.py "assets/historical taxonomy mapping(BI _ Internal_2026-01-13-1011).csv"
```

### With Custom Target ID

```bash
uv run src/ingest_historical_mapping.py "assets/historical taxonomy mapping(BI _ Internal_2026-01-13-1011).csv" --id "bi_internal_2026"
```

### Clear Existing Mappings

```bash
uv run src/ingest_historical_mapping.py "assets/historical taxonomy mapping(BI _ Internal_2026-01-13-1011).csv" --id "bi_internal_2026" --clear
```

**Expected Output:**
```
Loading historical mapping from assets/historical taxonomy mapping(BI _ Internal_2026-01-13-1011).csv...
Loaded 15525 historical mappings
Creating documents...
Ingesting 15525 historical mappings into vectorstore...
Successfully ingested 15525 historical mapping embeddings
Target ID: historical_mapping
```

## Step 2: Run Historical Matching

Match your target taxonomy against the historical mappings.

### Basic Usage (Default Settings)

```bash
uv run src/historical_matcher.py assets/zalando_taxonomy.csv
```

This will:
- Use `source-id="historical_mapping"` (default)
- Create embeddings on the fly from the CSV
- Search against historical mappings
- Output results to `results/zalando_taxonomy/{timestamp}/`

### With Pre-Ingested Client Taxonomy

If you've already ingested the client taxonomy embeddings:

```bash
# First, ingest client taxonomy
uv run src/ingest_taxonomy.py assets/zalando_taxonomy.csv --id zalando

# Then match using pre-existing embeddings
uv run src/historical_matcher.py assets/zalando_taxonomy.csv --target-id zalando
```

### With Custom Source ID

To search against a different historical mapping set:

```bash
uv run src/historical_matcher.py assets/zalando_taxonomy.csv --source-id "bi_internal_2026"
```

### With Custom Threshold

```bash
uv run src/historical_matcher.py assets/zalando_taxonomy.csv --threshold 0.7
```

### Full Example

```bash
uv run src/historical_matcher.py assets/zalando_taxonomy.csv \
  --source-id "historical_mapping" \
  --target-id "zalando" \
  --threshold 0.6
```

**Expected Output:**
```
Loading target taxonomy...
Loaded 213 categories from target taxonomy
Found source embeddings in database (source_id: historical_mapping)
Retrieving embeddings for target_id 'zalando' from database...
Retrieved 213 embeddings for target_id 'zalando'
Matching categories to historical mappings...
Generating outputs...
Completed in 45.23 seconds
Matched 195 out of 213 categories
```

**Generated Files:**
- `results/zalando_taxonomy/{timestamp}/matched_csv.csv` - Updated taxonomy with GDW_SUBCATEGORY filled
- `results/zalando_taxonomy/{timestamp}/detailed_report.csv` - Detailed matching information
- `results/zalando_taxonomy/{timestamp}/summary_statistics.json` - Summary statistics

## Step 3: Compare Results

Compare matching results from different methods or runs.

### Compare Two Detailed Reports

The comparison tool expects CSV files with columns: `L2`, `L3`, `matched_l2`, `matched_l3`.

**Note:** The detailed_report.csv uses `target_l2` and `target_l3` instead of `L2` and `L3`. You may need to rename columns or use a different file format.

### Option 1: Compare Detailed Reports (Manual Column Mapping)

If comparing detailed_report.csv files, you'll need to rename columns first:

```bash
# Create a script or manually rename columns:
# target_l2 → L2
# target_l3 → L3
# matched_l2 → matched_l2 (already correct)
# matched_l3 → matched_l3 (already correct)
```

### Option 2: Compare Using Matched CSV Files

If you have matched CSV files with the correct column names:

```bash
uv run src/compare_results.py \
  results/zalando_taxonomy/20260114_165125/detailed_report.csv \
  results/zalando_taxonomy/20260115_120000/detailed_report.csv \
  --output-dir results/comparison
```

### Example: Compare Historical vs Embeddings Matcher

```bash
# Run embeddings matcher
uv run src/embeddings_matcher.py assets/zalando_taxonomy.csv

# Run historical matcher
uv run src/historical_matcher.py assets/zalando_taxonomy.csv

# Compare results (after renaming columns if needed)
uv run src/compare_results.py \
  results/zalando_taxonomy/{embeddings_timestamp}/detailed_report.csv \
  results/zalando_taxonomy/{historical_timestamp}/detailed_report.csv \
  --output-dir results/comparison/historical_vs_embeddings
```

**Expected Output:**
```
Loading reference file: results/zalando_taxonomy/20260114_165125/detailed_report.csv
Loading evaluation file: results/zalando_taxonomy/20260115_120000/detailed_report.csv

Validating that L2 and L3 columns are identical...
✓ L2 and L3 columns are identical

Comparing matched_l2...
✓ Generated matched_l2 confusion matrix

Comparing matched_l2 + matched_l3...
✓ Generated matched_l2_l3 confusion matrix

Creating summary plots...
✓ Generated summary comparison plot

✓ All outputs saved to: results/comparison
```

**Generated Files:**
- `results/comparison/matched_l2_confusion_matrix.png` - L2 comparison matrix
- `results/comparison/matched_l2_l3_confusion_matrix.png` - L2+L3 comparison matrix
- `results/comparison/summary_comparison.png` - Summary statistics plot

## Complete Workflow Example

Here's a complete end-to-end example:

```bash
# 1. Start database
docker-compose up -d

# 2. Ingest historical mappings
uv run src/ingest_historical_mapping.py \
  "assets/historical taxonomy mapping(BI _ Internal_2026-01-13-1011).csv" \
  --id "bi_internal_2026"

# 3. (Optional) Ingest client taxonomy for faster matching
uv run src/ingest_taxonomy.py assets/zalando_taxonomy.csv --id zalando

# 4. Run historical matching
uv run src/historical_matcher.py assets/zalando_taxonomy.csv \
  --source-id "bi_internal_2026" \
  --target-id "zalando" \
  --threshold 0.6

# 5. Compare with another method (e.g., embeddings matcher)
uv run src/embeddings_matcher.py assets/zalando_taxonomy.csv --id zalando

# 6. Compare results (after preparing CSV files with correct column names)
uv run src/compare_results.py \
  results/zalando_taxonomy/{embeddings_timestamp}/detailed_report.csv \
  results/zalando_taxonomy/{historical_timestamp}/detailed_report.csv \
  --output-dir results/comparison
```

## Troubleshooting

### No Historical Mappings Found

If you get "No historical mappings found", ensure you've ingested them first:

```bash
uv run src/ingest_historical_mapping.py "path/to/historical_mapping.csv"
```

### Column Name Mismatch in Comparison

The `compare_results.py` expects columns `L2`, `L3`, `matched_l2`, `matched_l3`, but `detailed_report.csv` uses `target_l2`, `target_l3`. You can:

1. Rename columns in the CSV before comparison
2. Use a different output file that has the correct column names
3. Modify the comparison script to handle both formats

### Database Connection Issues

Ensure PostgreSQL is running:

```bash
docker-compose ps
docker-compose logs postgres
```

## Output Files Reference

### Historical Matcher Outputs

- **matched_csv.csv**: Updated taxonomy with `GDW_SUBCATEGORY` column filled
- **detailed_report.csv**: Contains:
  - `target_l1`, `target_l2`, `target_l3`: Original categories
  - `matched_l2`, `matched_l3`: Matched categories from historical mapping
  - `confidence`: Match confidence score
  - `method_used`: "historical_mapping"
  - `top_3_candidates`: JSON array of top candidates
  - `reasoning`: Explanation of the match
- **summary_statistics.json**: Aggregate statistics (total matches, average confidence, etc.)

### Comparison Outputs

- **matched_l2_confusion_matrix.png**: Confusion matrix for L2 matches
- **matched_l2_l3_confusion_matrix.png**: Confusion matrix for L2+L3 combination matches
- **summary_comparison.png**: Visual summary of comparison statistics
