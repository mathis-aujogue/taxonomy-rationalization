"""API-friendly version of generate_descriptions with custom prompt support."""

import pandas as pd
from pathlib import Path
from typing import Optional
from tqdm import tqdm
from langchain_core.messages import SystemMessage, HumanMessage

from lib.services import TaxonomyServices
from utils.data.data_loader import load_taxonomy_csv
from ingest_taxonomy import extract_taxonomy_fields


def generate_prompt(fields: dict, template: Optional[str] = None) -> str:
    """Generate the prompt for description generation."""
    if template:
        # Use custom template with field substitution
        prompt = template.format(
            l1=fields.get("l1", ""),
            l2=fields.get("l2", ""),
            l3=fields.get("l3", ""),
            definition=fields.get("definition", ""),
        )
        return prompt

    # Default template
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


async def generate_descriptions_api(
    input_path: str,
    output_path: str,
    prompt_template: Optional[str] = None,
    llm_model: Optional[str] = None,
    limit: Optional[int] = None,
):
    """Generate descriptions for the taxonomy with custom prompt support."""
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = load_taxonomy_csv(input_path)

    if limit:
        df = df.head(limit)

    # Initialize services
    services = TaxonomyServices()
    await services.post_init()

    # Override LLM if specified (would need to modify services for this)
    # For now, use default LLM from services

    descriptions = []
    pbar = tqdm(total=len(df), desc="Generating")

    try:
        for idx, row in df.iterrows():
            fields = extract_taxonomy_fields(row)

            # Skip if essential fields are missing
            if not fields.get("l3") and not fields.get("l2"):
                descriptions.append("")
                pbar.update(1)
                continue

            prompt = generate_prompt(fields, prompt_template)

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
