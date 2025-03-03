## Prompt for LLM model to pass with CSV files and get json output of filtered contracts

prompt = """
    I have the following CSV files: 

    Process these files with the following parameters: 
    
    You are an expert contract analyst for the Department of Government Efficiency (DOGE) as of March 3, 2025. Analyze the attached CSV of government contracts to identify:
    1. **DEI Contracts**: Live contracts (end date after 3/3/2025) with "diversity," "equity," "inclusion," "DEI," "DEIA," or "DEBIA" in `prime_award_base_transaction_description`. These align with the Executive Order targeting DEI waste.
    2. **DOGE Targets**: Live contracts (end date after 3/3/2025) indicating potential fraud, waste, or abuse per doge.gov/savings—e.g., amounts >$1M, vague descriptions ("support services," "consulting," "training," "management" without specifics), or non-essential spending (e.g., travel, cultural fluff).

    For each:
    - Extract `award_id_piid`, `current_total_value_of_award`, `prime_award_base_transaction_description`, `period_of_performance_current_end_date`.
    - Flag if live (end date > 3/3/2025).
    - Output as two JSON lists: `dei_contracts` and `doge_targets`.

    Rules:
    - Case-insensitive keyword search.
    - Ignore terminated/expired rows (end date ≤ 3/3/2025).
    - For DOGE, prioritize high amounts (>10M) or vague terms unless clearly mission-critical (e.g., "aircraft maintenance" is fine, "training" alone isn’t).
    - If unsure, err on flagging for review.

    Example Output:
    {
    "dei_contracts": [
        {"piid": "75P00123P00067", "amount": 3726500, "description": "DIVERSITY, EQUITY, INCLUSION & ACCESSIBILITY CONTRACT", "end_date": "2025-07-19", "live": true}
    ],
    "doge_targets": [
        {"piid": "SAQMMA15F0999", "amount": 426576765.45, "description": "ETS2 TRAVEL SERVICES", "end_date": "2027-06-03", "live": true}
    ]
    }
    """
