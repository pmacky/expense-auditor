# auditor.py
import json
import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Only Groq now — completely free!
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ─────────────────────────────────────────
# AGENT 1: Receipt Extractor
# ─────────────────────────────────────────
def agent_extract_receipt(receipt_text):
    print("🔍 Agent 1: Extracting receipt data...")

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """You are a receipt data extraction specialist.
                Extract structured data from receipt text.
                Always respond with ONLY a JSON object, no extra text, no markdown backticks."""
            },
            {
                "role": "user",
                "content": f"""Extract the following from this receipt text:
                - merchant (business name, usually at the top)
                - amount (look for TOTAL, BALANCE, AMOUNT DUE first.
                  If those are unreadable, add up all item prices you can see.
                  Return a single clean number like $35.01 — no text, no calculations shown)
                - date (in DD/MM/YYYY format)
                - category (one of: Meals, Transport, Lodging, Entertainment, Office Supplies, Other)
                - items (list of purchased items)

                Receipt text:
                {receipt_text}

                Respond ONLY with JSON:
                {{
                    "merchant": "...",
                    "amount": "$XX.XX",
                    "date": "DD/MM/YYYY",
                    "category": "...",
                    "items": ["item1", "item2"]
                }}"""
            }
        ]
    )

    text = response.choices[0].message.content
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


# ─────────────────────────────────────────
# AGENT 2: Policy Searcher
# ─────────────────────────────────────────
def agent_search_policy(policy_text, category, amount):
    print("📋 Agent 2: Searching policy for relevant rules...")

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """You are a corporate policy search specialist.
                Find and extract ONLY the policy rules relevant to a specific expense.
                Always respond with ONLY a JSON object, no extra text, no markdown backticks."""
            },
            {
                "role": "user",
                "content": f"""From this company policy, extract ALL rules
                that apply to a '{category}' expense of {amount}.

                Focus on:
                - Spending limits for this category
                - Any prohibitions or restrictions
                - Location based rules if mentioned
                - Approval requirements

                Policy document:
                {policy_text[:3000]}

                Respond ONLY with JSON like this:
                {{
                    "relevant_rules": ["rule 1", "rule 2"],
                    "spending_limit": "...",
                    "prohibitions": ["..."],
                    "policy_snippet": "the most relevant quote from the policy"
                }}"""
            }
        ]
    )

    text = response.choices[0].message.content
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


# ─────────────────────────────────────────
# AGENT 3: Auditor
# ─────────────────────────────────────────
def agent_audit(extracted_data, policy_rules, business_purpose, claimed_date=None): 
    print("⚖️  Agent 3: Making audit decision...")

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """You are a senior corporate expense auditor with 20 years experience.
                You are strict but fair. You make clear justified decisions.
                Always respond with ONLY a JSON object, no extra text, no markdown backticks."""
            },
            {
                "role": "user",
                "content": f"""Audit this expense claim:

                RECEIPT DATA:
                {json.dumps(extracted_data, indent=2)}

                EMPLOYEE BUSINESS PURPOSE:
                "{business_purpose}"

                EMPLOYEE CLAIMED DATE: {claimed_date or 'Not provided'}

                DATE VALIDATION: Check if the date on the receipt matches
                the claimed date. If they are more than 7 days apart, flag it.
                If the receipt date is more than 90 days old, reject it.

                RELEVANT POLICY RULES:
                {json.dumps(policy_rules, indent=2)}

                Make an audit decision. Respond ONLY with JSON:
                {{
                    "status": "Approved" or "Flagged" or "Rejected",
                    "reason": "One sentence citing the specific rule",
                    "confidence": "High" or "Medium" or "Low",
                    "flags": ["list of specific concerns if any"]
                }}"""
            }
        ]
    )

    text = response.choices[0].message.content
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


# ─────────────────────────────────────────
# AGENT 4: Fraud Risk Scorer
# ─────────────────────────────────────────
def agent_score_risk(extracted_data, business_purpose, audit_result):
    print("🚨 Agent 4: Calculating fraud risk score...")

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": """You are a fraud detection specialist for corporate expenses.
                You identify suspicious patterns in expense claims.
                Always respond with ONLY a JSON object, no extra text, no markdown backticks."""
            },
            {
                "role": "user",
                "content": f"""Calculate a fraud risk score (0-100) for this expense:

                CLAIM DATA:
                {json.dumps(extracted_data, indent=2)}

                BUSINESS PURPOSE: "{business_purpose}"
                AUDIT RESULT: {audit_result['status']}

                Check for these red flags:
                - Round number amounts ($50.00, $100.00 exactly)
                - Vague business purpose
                - Missing receipt details
                - Amount suspiciously close to policy limit
                - Unusual category

                Respond ONLY with JSON:
                {{
                    "risk_score": 0-100,
                    "risk_level": "Low" or "Medium" or "High",
                    "red_flags": ["flag1", "flag2"],
                    "explanation": "one sentence summary"
                }}"""
            }
        ]
    )

    text = response.choices[0].message.content
    text = text.replace("```json", "").replace("```", "").strip()
    return json.loads(text)


# ─────────────────────────────────────────
# MAIN PIPELINE
# ─────────────────────────────────────────
def run_audit_pipeline(receipt_text, business_purpose, policy_text, claimed_date=None):
    print("\n🚀 Starting multi-agent audit pipeline...\n")

    extracted = agent_extract_receipt(receipt_text)
    policy    = agent_search_policy(policy_text, extracted["category"], extracted["amount"])
    audit     = agent_audit(extracted, policy, business_purpose, claimed_date)
    risk      = agent_score_risk(extracted, business_purpose, audit)

    result = {
        "merchant":       extracted["merchant"],
        "amount":         extracted["amount"],
        "date":           extracted["date"],
        "category":       extracted["category"],
        "items":          extracted.get("items", []),
        "status":         audit["status"],
        "reason":         audit["reason"],
        "confidence":     audit["confidence"],
        "flags":          audit["flags"],
        "risk_score":     risk["risk_score"],
        "risk_level":     risk["risk_level"],
        "red_flags":      risk["red_flags"],
        "policy_snippet": policy.get("policy_snippet", ""),
        "relevant_rules": policy.get("relevant_rules", [])
    }

    print(f"\n✅ Pipeline complete! Status: {result['status']} | Risk: {result['risk_score']}/100\n")
    return result