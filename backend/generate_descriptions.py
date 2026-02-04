"""
Script to generate descriptions for taxonomy categories using LLM.
Reads a taxonomy CSV, generates descriptions for each category, and saves the enriched CSV.
"""

import asyncio
import argparse
from typing import Optional
from pathlib import Path
from tqdm import tqdm
from langchain_core.messages import SystemMessage, HumanMessage

from lib.services import TaxonomyServices
from utils.ui.progress import setup_logging
from utils.data.data_loader import load_taxonomy_csv
from ingest_taxonomy import extract_taxonomy_fields


def generate_prompt(fields: dict) -> str:
    """Generate the prompt for description generation."""
    l1 = fields.get("l1", "")
    l2 = fields.get("l2", "")
    l3 = fields.get("l3", "")
    existing_def = fields.get("definition", "")

    prompt = f"""Generate a detailed 1-2 sentence description for this expense category.
    
Context:
- L1 (High level): {l1}
- L2 (Mid level): {l2}
- L3 (Specific): {l3}
"""
    if existing_def:
        prompt += f"- Existing Definition: {existing_def}\n"

    prompt += """
Requirements:
- Describe what kind of expenses belong here.
- Provide specific examples if applicable.
- Clarify distinguishing features from similar categories.
- Output ONLY the description, no intro/outro.
"""
    return prompt


async def generate_descriptions(input_path: str, output_path: str, limit: Optional[int] = None):
    """Generate descriptions for the taxonomy."""
    setup_logging()
    
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    print(f"Loading taxonomy from {input_path}...")
    df = load_taxonomy_csv(input_path)
    
    if limit:
        df = df.head(limit)
        print(f"Limiting to first {limit} rows.")

    # Initialize services
    services = TaxonomyServices()
    await services.post_init()
    
    print("Generating descriptions...")
    descriptions = []
    
    # Create progress bar
    pbar = tqdm(total=len(df), desc="Generating")
    
    try:
        for idx, row in df.iterrows():
            fields = extract_taxonomy_fields(row)
            
            # Skip if essential fields are missing (e.g. empty row)
            if not fields.get("l3") and not fields.get("l2"):
                descriptions.append("")
                pbar.update(1)
                continue
                
            prompt = generate_prompt(fields)
            
            try:
                # Call LLM
                response = await services.llm.ainvoke([
                    SystemMessage(content="You are an expert in procurement and expense categorization."),
                    HumanMessage(content=prompt)
                ])
                description = str(response.content).strip()
                descriptions.append(description)
            except Exception as e:
                print(f"\nError generating description for row {idx}: {e}")
                descriptions.append("")
                
            pbar.update(1)
            
    finally:
        await services.aclose()
        pbar.close()

    # Add to DataFrame
    df["generated_description"] = descriptions
    
    # Save to output
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_file, index=False)
    print(f"Saved enriched taxonomy to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate descriptions for taxonomy categories.")
    parser.add_argument("input_csv", help="Path to input taxonomy CSV")
    parser.add_argument("output_csv", help="Path to output CSV")
    parser.add_argument("--limit", type=int, help="Limit number of rows for testing")
    
    args = parser.parse_args()
    
    asyncio.run(generate_descriptions(args.input_csv, args.output_csv, args.limit))


if __name__ == "__main__":
    main()
