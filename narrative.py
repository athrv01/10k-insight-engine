"""
narrative.py
------------
Turns computed ratios + flagged anomalies into an analyst-style written
summary using the Claude API.

Requires an Anthropic API key in the ANTHROPIC_API_KEY environment variable.
Get one at https://console.anthropic.com/
"""

import os
import json
import anthropic


def build_prompt(company_name: str, ratio_series: dict, flags: dict) -> str:
    """
    Assembles a structured prompt from the numeric data so Claude has
    everything it needs to write a grounded, non-hallucinated summary.
    """
    return f"""You are a junior equity research analyst writing a concise
internal note. You have been given computed financial ratios for
{company_name} across multiple fiscal years, plus a list of ratios that
moved more than 20% year-over-year (potential areas worth flagging).

RATIO DATA (by fiscal year):
{json.dumps(ratio_series, indent=2)}

FLAGGED YEAR-OVER-YEAR MOVES (ratio, % change):
{json.dumps(flags, indent=2)}

Write a short analyst note (250-350 words) with this structure:
1. One-paragraph overview of the company's financial trajectory
2. Liquidity & leverage: any concerns or strengths
3. Profitability trend: is it improving, deteriorating, or stable, and why it might matter
4. 2-3 specific things a human analyst should dig into further, based on
   the flagged anomalies above

Be specific and reference actual numbers. Do not invent data that isn't
in the tables above. Write in plain, direct analyst language — no fluff,
no generic disclaimers."""


def generate_narrative(company_name: str, ratio_series: dict, flags: dict) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise EnvironmentError(
            "Set the ANTHROPIC_API_KEY environment variable before calling "
            "generate_narrative(). Get a key at https://console.anthropic.com/"
        )

    client = anthropic.Anthropic(api_key=api_key)
    prompt = build_prompt(company_name, ratio_series, flags)

    response = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    # Concatenate all text blocks in the response
    return "".join(block.text for block in response.content if block.type == "text")
