## Prompt for LLM model to pass with CSV files and get json output of filtered contracts

prompt = """
    I have the following CSV files: 

    Process these files with the following parameters: 
    
    You are an expert contract analyst for the Department of Government Efficiency (DOGE) as of March 4, 2025. Analyze the attached CSV of government contracts to identify:
    1. **DEI Contracts**: Live contracts (end date after 3/4/2025) with "diversity," "equity," "inclusion," "DEI," "DEIA," or "DEBIA" in `prime_award_base_transaction_description`. These align with the Executive Order targeting DEI waste.
    2. **DOGE Targets**: Live contracts (end date after 3/4/2025) indicating potential fraud, waste, or abuse per doge.gov/savings—e.g., amounts >$1M, vague descriptions ("support services," "consulting," "training," "management" without specifics), or non-essential spending (e.g., travel, cultural fluff).

    For each:
    - Extract `award_id_piid`, `current_total_value_of_award`, `prime_award_base_transaction_description`, `period_of_performance_current_end_date` and `recipient_name`.
    - Flag if live (end date > 3/4/2025).
    - Double check if the contract is live by using the https://www.USASpending.gov or https://www.fpds.gov/ search and making sure thare are no modifications to the contract that terminite it. E.g. "terminted for convinience" or updated end date is before today (March 04, 2025)
    - Output as two JSON lists: `dei_contracts` and `doge_targets`.

    Rules:
    - Go to https://doge.gov/savings and look at the contract descriptions in the list ot understand the mission criticality. Use the descriptions on the websiteto flag contracts on the provided text.
    - Case-insensitive keyword search.
    - Ignore terminated/expired rows (end date ≤ 3/4/2025).
    - For DOGE, prioritize any amount or vague terms unless clearly mission-critical (e.g., "aircraft maintenance" is fine, "training" alone isn’t).
    - If unsure, err on flagging for review.    
    - Make output JSON as compact as possible only including `id`, `amount` and `recipient`.

    Example Output:
    {   
    "dei_contracts": [
        {"id": "75P00123P00067", "amount": 3726500, "recipient": "Me, LLC"}
    ],
    "doge_targets": [
        {"id": "SAQMMA15F0999", "amount": 426576765.45, "recipient": "Me, LLC"}
    ]
    }
    """
