# Vector Comparison Process: Historical Matching

This document shows exactly what vector comparisons take place when matching `test.csv` against `historical_mapping.csv`.

## Data Structure

### Historical Mapping CSV (`historical_mapping.csv`)
Contains historical associations:
- **L2, L3**: Client categories (what gets embedded for matching)
- **matched_l2, matched_l3**: Our taxonomy categories (stored in metadata)

### Test CSV (`test.csv`)
Contains target categories to match:
- **L2, L3**: Categories to match (what gets embedded as query)
- **matched_l2, matched_l3**: (May be pre-filled or empty - will be filled by matching)

## Step-by-Step Vector Comparison Process

### Step 1: Ingestion Phase (Historical Mapping)

For each row in `historical_mapping.csv`, an embedding is created:

#### Example Row 1 from Historical Mapping:
```
L2: "COATING & FINISHING"
L3: "MFG, ENG & QUALITY SERVICES"
matched_l2: "PAINTING SERVICES"
matched_l3: "REAL ESTATE & FACILITIES"
```

**What gets embedded:**
```
Text: "COATING & FINISHING > MFG, ENG & QUALITY SERVICES"
↓
Embedding Vector: [0.123, -0.456, 0.789, ..., 0.234] (1536 dimensions)
```

**What gets stored in metadata:**
```json
{
  "target_id": "historical_mapping",
  "l2": "COATING & FINISHING",
  "l3": "MFG, ENG & QUALITY SERVICES",
  "matched_l2": "PAINTING SERVICES",
  "matched_l3": "REAL ESTATE & FACILITIES"
}
```

#### Example Row 2 from Historical Mapping:
```
L2: "COURIER SERVICES"
L3: "TRANSPORTATION & LOGISTICS"
matched_l2: "COURIER SERVICES"
matched_l3: "TRANSPORTATION & LOGISTICS"
```

**Embedding:**
```
Text: "COURIER SERVICES > TRANSPORTATION & LOGISTICS"
↓
Embedding Vector: [0.234, -0.567, 0.890, ..., 0.345]
```

#### Example Row 3 from Historical Mapping:
```
L2: "CUSTOMER LOYALTY PROGRAMS"
L3: "MARKETING"
matched_l2: "PROMOTIONS & CUSTOMER LOYALTY"
matched_l3: "MARKETING"
```

**Embedding:**
```
Text: "CUSTOMER LOYALTY PROGRAMS > MARKETING"
↓
Embedding Vector: [0.345, -0.678, 0.901, ..., 0.456]
```

**Result:** ~15,525 embeddings stored in vector database, each with metadata containing the matched categories.

---

### Step 2: Matching Phase (Test CSV)

For each row in `test.csv`, a query embedding is created and compared:

#### Query 1: First Row from Test CSV
```
L2: "COATING & FINISHING"
L3: "MFG, ENG & QUALITY SERVICES"
```

**Query Embedding Created:**
```
Text: "COATING & FINISHING > MFG, ENG & QUALITY SERVICES"
↓
Query Vector: [0.123, -0.456, 0.789, ..., 0.234] (1536 dimensions)
```

**Vector Search Process:**
1. Calculate cosine similarity (or distance) between query vector and ALL historical mapping vectors
2. Find top 5 most similar vectors (k=5)

**Example Similarity Scores:**
```
Historical Mapping Row 1: "COATING & FINISHING > MFG, ENG & QUALITY SERVICES"
  → Similarity: 0.98 (very high - exact match!)
  → Distance: 0.02

Historical Mapping Row 2: "COURIER SERVICES > TRANSPORTATION & LOGISTICS"
  → Similarity: 0.15 (low - different category)
  → Distance: 0.85

Historical Mapping Row 3: "CUSTOMER LOYALTY PROGRAMS > MARKETING"
  → Similarity: 0.12 (low - different category)
  → Distance: 0.88

... (continues for all 15,525 historical mappings)
```

**Top Match Found:**
```
Best Match: Historical Mapping Row 1
  - Similarity: 0.98
  - Confidence Score: 0.98 (after normalization)
  - Metadata Retrieved:
    * matched_l2: "PAINTING SERVICES"
    * matched_l3: "REAL ESTATE & FACILITIES"
```

**Result for Query 1:**
```
Input:  L2="COATING & FINISHING", L3="MFG, ENG & QUALITY SERVICES"
Output: matched_l2="PAINTING SERVICES", matched_l3="REAL ESTATE & FACILITIES"
```

---

#### Query 2: Second Row from Test CSV
```
L2: "COURIER SERVICES"
L3: "TRANSPORTATION & LOGISTICS"
```

**Query Embedding:**
```
Text: "COURIER SERVICES > TRANSPORTATION & LOGISTICS"
↓
Query Vector: [0.234, -0.567, 0.890, ..., 0.345]
```

**Vector Search:**
```
Historical Mapping Row 2: "COURIER SERVICES > TRANSPORTATION & LOGISTICS"
  → Similarity: 0.99 (exact match!)
  → Distance: 0.01

Historical Mapping Row 1: "COATING & FINISHING > MFG, ENG & QUALITY SERVICES"
  → Similarity: 0.15
  → Distance: 0.85

... (continues)
```

**Result for Query 2:**
```
Input:  L2="COURIER SERVICES", L3="TRANSPORTATION & LOGISTICS"
Output: matched_l2="COURIER SERVICES", matched_l3="TRANSPORTATION & LOGISTICS"
```

---

#### Query 3: Third Row from Test CSV
```
L2: "CUSTOMER LOYALTY PROGRAMS"
L3: "MARKETING"
```

**Query Embedding:**
```
Text: "CUSTOMER LOYALTY PROGRAMS > MARKETING"
↓
Query Vector: [0.345, -0.678, 0.901, ..., 0.456]
```

**Vector Search:**
```
Historical Mapping Row 3: "CUSTOMER LOYALTY PROGRAMS > MARKETING"
  → Similarity: 0.97 (very high match)
  → Distance: 0.03

Historical Mapping Row 1: "COATING & FINISHING > MFG, ENG & QUALITY SERVICES"
  → Similarity: 0.18
  → Distance: 0.82

... (continues)
```

**Result for Query 3:**
```
Input:  L2="CUSTOMER LOYALTY PROGRAMS", L3="MARKETING"
Output: matched_l2="PROMOTIONS & CUSTOMER LOYALTY", matched_l3="MARKETING"
```

---

## Visual Summary

```
┌─────────────────────────────────────────────────────────────┐
│ HISTORICAL MAPPING DATABASE (15,525 embeddings)            │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Row 1: "COATING & FINISHING > MFG, ENG & QUALITY SERVICES" │
│   Vector: [0.123, -0.456, ..., 0.234]                       │
│   Metadata: {matched_l2: "PAINTING SERVICES", ...}          │
│                                                              │
│ Row 2: "COURIER SERVICES > TRANSPORTATION & LOGISTICS"      │
│   Vector: [0.234, -0.567, ..., 0.345]                        │
│   Metadata: {matched_l2: "COURIER SERVICES", ...}          │
│                                                              │
│ Row 3: "CUSTOMER LOYALTY PROGRAMS > MARKETING"             │
│   Vector: [0.345, -0.678, ..., 0.456]                       │
│   Metadata: {matched_l2: "PROMOTIONS & CUSTOMER LOYALTY"}  │
│                                                              │
│ ... (15,522 more rows)                                      │
└─────────────────────────────────────────────────────────────┘
                            ↑
                            │ Vector Search
                            │ (Cosine Similarity)
                            │
┌─────────────────────────────────────────────────────────────┐
│ TEST CSV QUERIES (100 queries)                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ Query 1: "COATING & FINISHING > MFG, ENG & QUALITY SERVICES"│
│   Vector: [0.123, -0.456, ..., 0.234]                       │
│   → Matches Row 1 (similarity: 0.98)                        │
│   → Returns: matched_l2="PAINTING SERVICES"                 │
│                                                              │
│ Query 2: "COURIER SERVICES > TRANSPORTATION & LOGISTICS"   │
│   Vector: [0.234, -0.567, ..., 0.345]                        │
│   → Matches Row 2 (similarity: 0.99)                        │
│   → Returns: matched_l2="COURIER SERVICES"                  │
│                                                              │
│ Query 3: "CUSTOMER LOYALTY PROGRAMS > MARKETING"           │
│   Vector: [0.345, -0.678, ..., 0.456]                        │
│   → Matches Row 3 (similarity: 0.97)                        │
│   → Returns: matched_l2="PROMOTIONS & CUSTOMER LOYALTY"     │
│                                                              │
│ ... (97 more queries)                                        │
└─────────────────────────────────────────────────────────────┘
```

## Key Points

1. **Embedding Creation**: Both historical mappings and test queries use the same format: `"L2 > L3"` (no definition)

2. **Vector Comparison**: Uses cosine similarity (or distance) in 1536-dimensional space

3. **Top-K Retrieval**: For each query, finds top 5 most similar historical mappings

4. **Metadata Extraction**: After finding the best match, extracts `matched_l2` and `matched_l3` from the matched document's metadata

5. **Confidence Scoring**: Similarity scores are converted to confidence scores (0.0-1.0) using a normalization function

## Example: Exact Match vs. Similar Match

### Exact Match (High Confidence)
```
Query:    "COATING & FINISHING > MFG, ENG & QUALITY SERVICES"
Match:    "COATING & FINISHING > MFG, ENG & QUALITY SERVICES"
Similarity: 0.98
Confidence: 0.98
Result: matched_l2="PAINTING SERVICES", matched_l3="REAL ESTATE & FACILITIES"
```

### Similar Match (Medium Confidence)
```
Query:    "Cleaning Services > Facility Management"
Match:    "Cleaning Supplies > MRO Supplies"  (from historical mapping)
Similarity: 0.72
Confidence: 0.72
Result: matched_l2="JANITORIAL SUPPLIES", matched_l3="MRO"
```

### No Good Match (Low Confidence)
```
Query:    "New Category > New Subcategory"
Match:    "Somewhat Related > Category"  (best available, but not great)
Similarity: 0.45
Confidence: 0.45
Result: matched_l2="", matched_l3=""  (if below threshold)
```

## Performance Characteristics

- **Embedding Creation**: ~2-3 seconds per 100 categories
- **Vector Search**: ~0.1-0.5 seconds per query (with pgvector index)
- **Total Time**: ~10-30 seconds for 100 queries

The vector search is optimized using pgvector's HNSW index for fast approximate nearest neighbor search.
