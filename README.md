# 🎯 Taxonomy Rationalization

**AI-Powered Category Matching System**

Automatically match client taxonomies to your internal taxonomy using state-of-the-art AI techniques. This project provides three powerful matching strategies to ensure accurate, scalable category mapping for enterprise spend analysis.

---

## 📋 Overview

When working with multiple clients, each may use different category taxonomies to classify their spending. This project solves the challenge of mapping client-specific categories to a standardized internal taxonomy, enabling:

- **Unified spend analysis** across multiple clients
- **Automated category matching** at scale
- **High accuracy** matching using AI/ML techniques
- **Transparent decision-making** with confidence scores and reasoning

### The Problem

```
Client Taxonomy                    →    Internal Taxonomy
─────────────────                        ─────────────────
Canteen Services                  →    FOOD SERVICES
Cleaning Services and goods       →    JANITORIAL SERVICES
Architecture, interior design...  →    ARCHITECTURAL SERVICES
```

Manual matching is:
- ❌ Time-consuming (hours per client)
- ❌ Error-prone (inconsistent decisions)
- ❌ Not scalable (hundreds of categories)
- ❌ Hard to audit (no reasoning trail)

---

## 🚀 Three Matching Strategies

The project offers three complementary approaches, each optimized for different use cases:

### 1. 🔍 Embeddings-Based Matching
**Fast & Efficient** | ~2-5 minutes for 200+ categories

- Uses semantic similarity via Azure OpenAI embeddings
- Vector search with pgvector (PostgreSQL extension)
- Best for: Large-scale matching with speed requirements
- **Performance**: Fastest, cost-effective

### 2. 🤖 LLM-Based Matching
**Most Accurate** | ~10-20 minutes for 200+ categories

- Direct matching using Azure OpenAI LLM (GPT-4)
- Understands context and definitions
- Best for: Complex categories requiring nuanced understanding
- **Performance**: Most accurate, slower, higher cost

### 3. ⚡ Hybrid Matching
**Best of Both Worlds** | ~5-10 minutes for 200+ categories

- Combines embeddings (fast filtering) + LLM (accurate selection)
- Gets top-k candidates via vector search, then LLM selects best match
- Best for: Production use cases requiring balance
- **Performance**: Balanced speed and accuracy

---

## 🏗️ Architecture

```
┌─────────────────┐
│ Client Taxonomy │  (CSV: COMMODITY_L1, L2, L3)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Matching Engine                   │
│  ┌──────────┐  ┌──────────┐        │
│  │Embeddings│  │   LLM    │        │
│  │ Matcher  │  │ Matcher  │        │
│  └────┬─────┘  └────┬─────┘        │
│       │             │               │
│       └──────┬──────┘               │
│              │                      │
│         ┌────▼────┐                 │
│         │ Hybrid  │                 │
│         │ Matcher │                 │
│         └────┬────┘                 │
└──────────────┼──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   PostgreSQL + pgvector             │
│   (Vector Embeddings Storage)      │
└─────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│   Output Files                      │
│  • Matched CSV                      │
│  • Detailed Report                  │
│  • Summary Statistics               │
└─────────────────────────────────────┘
```

---

## 📊 Key Features

### ✨ Intelligent Matching
- **Semantic understanding**: Matches based on meaning, not just keywords
- **Hierarchical context**: Considers L1, L2, L3 category relationships
- **Definition-aware**: Uses category definitions for better accuracy

### 📈 Confidence Scoring
- Every match includes a confidence score (0.0 - 1.0)
- Threshold-based filtering (configurable)
- Top-k candidate ranking for review

### 📝 Comprehensive Reporting
- **Detailed Reports**: Every match with reasoning, alternatives, scores
- **Summary Statistics**: Aggregate metrics, confidence distributions
- **Comparison Tools**: Compare different matching strategies side-by-side

### 🔄 Scalable & Production-Ready
- Batch processing for hundreds of categories
- Progress tracking with visual indicators
- Error handling and retry logic
- Docker-based PostgreSQL setup

---

## 🛠️ Quick Start

### Prerequisites

- Python 3.13+
- Docker & Docker Compose
- Azure OpenAI API keys
- `uv` package manager

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd taxonomy-rationalization

# Install dependencies
uv sync

# Set up environment variables
cp .env.example .env
# Edit .env with your Azure OpenAI credentials
```

### Basic Usage

```bash
# 1. Start PostgreSQL with pgvector
docker-compose up -d

# 2. Ingest our taxonomy (one-time setup)
uv run src/ingest_taxonomy.py --input-csv assets/our_taxonomy.csv

# 3. Run matching (choose your strategy)
uv run src/embeddings_matcher.py    # Fast
uv run src/llm_matcher.py           # Accurate
uv run src/hybrid_matcher.py        # Balanced
```

### Results

Results are saved in `results/` directory:
- `output_taxonomy.csv` - Updated taxonomy with matched categories
- `detailed_report.csv` - Complete matching details
- `summary.json` - Aggregate statistics

---

## 📁 Project Structure

```
taxonomy-rationalization/
├── assets/
│   ├── our_taxonomy.csv          # Internal taxonomy (reference)
│   └── their_taxonomy.csv        # Client taxonomy (to match)
├── src/
│   ├── embeddings_matcher.py     # Embeddings-based matching
│   ├── llm_matcher.py            # LLM-based matching
│   ├── hybrid_matcher.py         # Hybrid matching
│   ├── ingest_taxonomy.py        # Vector DB ingestion
│   ├── compare_results.py        # Compare matching strategies
│   └── utils/                    # Utilities & helpers
├── results/                      # Generated outputs
├── docker-compose.yml            # PostgreSQL setup
└── pyproject.toml                # Dependencies
```

---

## 📈 Example Output

### Input (Client Taxonomy)
```csv
DATA_SOURCE,COMMODITY_L1,COMMODITY_L2,COMMODITY_L3,GDW_SUBCATEGORY
ZALANDO,(Corporate) Property,Facility Management,Canteen Services,0
ZALANDO,(Corporate) Property,Facility Management,Cleaning Services,0
```

### Output (Matched Taxonomy)
```csv
DATA_SOURCE,COMMODITY_L1,COMMODITY_L2,COMMODITY_L3,GDW_SUBCATEGORY
ZALANDO,(Corporate) Property,Facility Management,Canteen Services,FOOD SERVICES
ZALANDO,(Corporate) Property,Facility Management,Cleaning Services,JANITORIAL SERVICES
```

### Detailed Report
| their_category_l3 | matched_category_l3 | confidence_score | reasoning |
|-------------------|---------------------|------------------|-----------|
| Canteen Services | FOOD SERVICES | 0.92 | High semantic similarity... |
| Cleaning Services | JANITORIAL SERVICES | 0.88 | Matches definition of... |

---

## 🎯 Use Cases

- **Spend Analytics**: Normalize spending data across multiple clients
- **Procurement**: Map vendor categories to internal standards
- **Compliance**: Ensure consistent categorization for reporting
- **Data Integration**: Standardize taxonomies during data onboarding

---

## 🔧 Configuration

### Environment Variables

```bash
# Azure OpenAI
AZURE_EMBEDDING_API_KEY=your_key
AZURE_CHAT_API_KEY=your_key
AZURE_EMBEDDING_ENDPOINT=https://...
AZURE_CHAT_ENDPOINT=https://...
AZURE_EMBEDDING_MODEL=text-embedding-ada-002
AZURE_CHAT_MODEL=gpt-4

# Database
DB_TYPE=local
LOCAL_POSTGRESQL_URL=postgresql://user:pass@localhost:5433/dbname
```

### Matching Parameters

- **Confidence Threshold**: Minimum score to accept a match (default: 0.6)
- **Top-K Candidates**: Number of alternatives to consider (default: 5)
- **Batch Size**: Categories processed per batch (default: 10)

---

## 📊 Performance Comparison

| Method | Speed | Accuracy | Cost | Best For |
|--------|-------|----------|------|----------|
| **Embeddings** | ⚡⚡⚡ Fast | ⭐⭐ Good | 💰 Low | Large batches |
| **LLM** | 🐌 Slow | ⭐⭐⭐ Excellent | 💰💰 Higher | Complex categories |
| **Hybrid** | ⚡⚡ Medium | ⭐⭐⭐ Very Good | 💰💰 Medium | Production use |

---

## 🧪 Testing & Validation

```bash
# Run unit tests
uv run pytest

# Compare matching strategies
uv run src/compare_results.py \
  --reference results/method1/detailed_report.csv \
  --evaluation results/method2/detailed_report.csv

# Generate comparison visualizations
# (Creates confusion matrices and summary charts)
```

---

## 📚 Documentation

- **[AGENTS.md](AGENTS.md)**: Comprehensive technical documentation
- **Code Comments**: Inline documentation in all modules
- **Type Hints**: Full type annotations for IDE support

---

## 🤝 Contributing

This project follows best practices:
- Type hints throughout
- Pydantic models for data validation
- Async/await for I/O operations
- Comprehensive error handling
- Progress tracking and logging

---

## 📄 License

[Add your license information here]

---

## 🙏 Acknowledgments

Built with:
- **Azure OpenAI** - Embeddings and LLM services
- **pgvector** - Vector similarity search
- **LangChain** - AI orchestration
- **PostgreSQL** - Robust data storage

---

## 📞 Support

For questions or issues:
1. Check [AGENTS.md](AGENTS.md) for detailed documentation
2. Review example outputs in `results/` directory
3. Inspect logs for debugging information

---

**Ready to rationalize your taxonomies?** 🚀

Start with: `uv run src/ingest_taxonomy.py --input-csv assets/our_taxonomy.csv`
