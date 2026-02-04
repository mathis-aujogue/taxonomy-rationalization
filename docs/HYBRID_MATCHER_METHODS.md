# Hybrid Matcher Methods Documentation

## Overview

The Hybrid Matcher is an advanced taxonomy matching system that combines multiple embedding-based signals to achieve high accuracy while maintaining fast performance. Unlike simpler matchers that use a single embedding per category, the hybrid matcher creates **five distinct embeddings** for each category and combines them using a weighted scoring system.

## Key Advantages

- **Multi-signal approach**: Uses 5 different embedding types for comprehensive matching
- **Fully offline**: Uses pre-computed embeddings stored in the database (no API calls during matching)
- **Hierarchical awareness**: Respects taxonomy hierarchy (L1 → L2 → L3)
- **Configurable weights**: Adjustable scoring weights for fine-tuning
- **Fast performance**: ~5-10 minutes for 200+ categories

---

## The Five Embedding Methods

The hybrid matcher creates five distinct embeddings for each category, each capturing different aspects of the taxonomy:

### 1. **L1 Embedding** (Level 1 - Most General)
- **What it captures**: The top-level category (e.g., "Property", "Banking Services")
- **Purpose**: Provides broad context and domain classification
- **Example**: 
  - Client: `(Corporate) Property`
  - Our: `PROPERTY`
  - **Use case**: Ensures matches stay within the same high-level domain

### 2. **L2 Embedding** (Level 2 - Middle Precision)
- **What it captures**: The second-level category (e.g., "Facility Management", "Banking Services")
- **Purpose**: Captures functional grouping within a domain
- **Example**:
  - Client: `Facility Management`
  - Our: `FACILITY MANAGEMENT`
  - **Use case**: Matches categories that serve similar functions

### 3. **L3 Embedding** (Level 3 - Most Specific)
- **What it captures**: The most specific category level (e.g., "Canteen Services", "Appraisals")
- **Purpose**: Precise category matching
- **Example**:
  - Client: `Canteen Services`
  - Our: `FOOD SERVICES`
  - **Use case**: Primary signal for exact category matching

### 4. **Full Path Embedding**
- **What it captures**: The complete hierarchical path as a single string
- **Format**: `"L1 > L2 > L3"` (e.g., `"Property > Facility Management > Canteen Services"`)
- **Purpose**: Captures hierarchical context and relationships
- **Example**:
  - Client: `Property > Facility Management > Canteen Services`
  - Our: `PROPERTY > FACILITY MANAGEMENT > FOOD SERVICES`
  - **Use case**: Understands how categories relate within their hierarchy

### 5. **Description Embedding**
- **What it captures**: The category definition/description text
- **Purpose**: Semantic understanding of what the category represents
- **Example**:
  - Client: `"Services for providing meals and food services to employees"`
  - Our: `"Companies that provide food and beverage services for corporate facilities"`
  - **Use case**: Matches categories with similar meanings even if names differ

---

## Scoring System

The hybrid matcher uses a **two-level weighted scoring system**:

### Level 1: Hierarchy Score

First, the three hierarchy levels (L1, L2, L3) are combined into a single hierarchy score:

```
hierarchy_score = (w_l1 × sim_l1) + (w_l2 × sim_l2) + (w_l3 × sim_l3)
```

**Default weights:**
- L1: `0.15` (15%)
- L2: `0.30` (30%)
- L3: `0.55` (55%)

**Rationale**: L3 (most specific) gets the highest weight because it's the most precise signal. L1 (most general) gets the lowest weight but still contributes to ensure domain consistency.

### Level 2: Final Score

The hierarchy score is then combined with the full path and description scores:

```
final_score = (w_hierarchy × hierarchy_score) + 
              (w_full_path × full_path_score) + 
              (w_description × description_score)
```

**Default weights:**
- Hierarchy: `0.30` (30%)
- Full Path: `0.20` (20%)
- Description: `0.50` (50%)

**Rationale**: Description gets the highest weight because it captures semantic meaning, which is crucial for accurate matching. Hierarchy ensures structural consistency, and full path provides additional context.

### Cosine Similarity

All similarity scores are calculated using **cosine similarity**:

```
cosine_similarity(v1, v2) = (v1 · v2) / (||v1|| × ||v2||)
```

This measures the angle between two vectors in embedding space, ranging from -1 (opposite) to 1 (identical), with 0 meaning orthogonal (unrelated).

---

## Matching Process

### Step 1: Embedding Generation (Pre-computation)

Before matching, embeddings must be generated and stored:

```bash
# From project root. Generate vectors for our taxonomy:
uv run backend/ingest_hybrid_embeddings.py assets/our_taxonomy_enriched.csv shq_hybrid

# Generate vectors for client taxonomy:
uv run backend/ingest_hybrid_embeddings.py assets/zalando_taxonomy_enriched.csv zalando_hybrid
```

**What happens:**
1. For each category row, extracts L1, L2, L3, full path, and description
2. Generates embeddings for each component using Azure OpenAI
3. Stores all 5 embeddings in the database with metadata indicating component type

### Step 2: Matching Execution

```bash
# From project root:
uv run backend/hybrid_matcher.py shq_hybrid zalando_hybrid
```

**What happens:**
1. **Loads cached embeddings** from database (no API calls)
2. For each client category:
   - Retrieves its 5 embeddings (L1, L2, L3, full, desc)
   - Compares against all target categories using cosine similarity
   - Calculates hierarchy score, full path score, and description score
   - Combines scores using weighted formula
   - Selects best match (highest final score)
3. Generates detailed report with confidence scores and top candidates

---

## Configuration

### Customizing Weights

You can customize the scoring weights by modifying the `DEFAULT_WEIGHTS` dictionary in `backend/hybrid_matcher.py`:

```python
DEFAULT_WEIGHTS = {
    "hierarchy": {
        "l1": 0.15,  # Adjust L1 weight
        "l2": 0.30,  # Adjust L2 weight
        "l3": 0.55   # Adjust L3 weight
    },
    "signals": {
        "hierarchy": 0.30,      # Weight for hierarchy score
        "full_path": 0.20,      # Weight for full path score
        "description": 0.50      # Weight for description score
    }
}
```

**Weight tuning guidelines:**
- **Increase description weight** if categories have rich definitions but names differ
- **Increase L3 weight** if category names are highly standardized
- **Increase full path weight** if hierarchy structure is very important
- **Ensure weights sum to 1.0** within each group for interpretability

---

## Output Format

### Detailed Report

The matcher generates a detailed CSV report with:

- `target_l1`, `target_l2`, `target_l3`: Original client categories
- `matched_l1`, `matched_l2`, `matched_l3`: Matched categories from our taxonomy
- `confidence`: Final weighted score (0.0 - 1.0)
- `reasoning`: Breakdown of hierarchy and description scores
- `top_3_candidates`: JSON array of top 3 matches with scores

### Example Output

```csv
target_l1,target_l2,target_l3,matched_l1,matched_l2,matched_l3,confidence,reasoning,top_3_candidates
Property,Facility Management,Canteen Services,PROPERTY,FACILITY MANAGEMENT,FOOD SERVICES,0.87,"Hierarchy: 0.82, Desc: 0.91",[{"l3":"FOOD SERVICES","score":0.87},...]
```

---

## Performance Characteristics

### Speed
- **Embedding generation**: ~2-3 minutes per taxonomy (one-time cost)
- **Matching**: ~5-10 minutes for 200+ categories (fully offline)

### Accuracy
- **High confidence matches** (>0.8): Typically 70-80% of categories
- **Medium confidence** (0.6-0.8): 15-20% of categories
- **Low confidence** (<0.6): 5-10% of categories (may require manual review)

### Cost
- **Embedding generation**: ~$0.01-0.02 per taxonomy (one-time)
- **Matching**: $0 (uses cached embeddings)

---

## Best Practices

1. **Always enrich taxonomies first**: Ensure descriptions are generated before creating vectors
   ```bash
   uv run backend/generate_descriptions.py assets/our_taxonomy.csv assets/our_taxonomy_enriched.csv
   ```

2. **Use descriptive target IDs**: Use clear identifiers like `shq_hybrid`, `zalando_hybrid` for easy tracking

3. **Review low-confidence matches**: Categories with confidence <0.6 should be manually reviewed

4. **Tune weights for your domain**: Different taxonomies may benefit from different weight configurations

5. **Monitor vector freshness**: Re-ingest when taxonomies are updated

---

## Troubleshooting

### "No embeddings found for target_id"
- **Solution**: Run `backend/ingest_hybrid_embeddings.py` first (or use the web UI Ingest step) to generate vectors

### Low confidence scores across the board
- **Possible causes**: 
  - Missing or poor-quality descriptions
  - Taxonomy structures are very different
  - Embedding model mismatch
- **Solutions**: 
  - Generate better descriptions
  - Adjust weights (increase description weight)
  - Verify embeddings were generated correctly

### Mismatches in expected domains
- **Solution**: Increase L1 weight to enforce domain consistency

---

## Technical Details

### Embedding Model
- **Model**: Azure OpenAI `text-embedding-ada-002`
- **Dimensions**: 1536
- **Storage**: PostgreSQL with pgvector extension

### Database Schema
Each embedding is stored with:
- `target_id`: Identifier for the taxonomy
- `component`: One of `'l1'`, `'l2'`, `'l3'`, `'full'`, `'desc'`
- `metadata`: JSON containing original category fields and index
- `embedding`: Vector representation (1536 dimensions)

### Vector Search
Uses PostgreSQL's pgvector extension for efficient cosine similarity search across all stored embeddings.
