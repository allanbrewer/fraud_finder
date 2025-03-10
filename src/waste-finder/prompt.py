## Prompt for LLM model to pass with CSV files and get json output of filtered contracts

dei_prompt = """
    I have the following CSV files: 

    Process these files with the following parameters: 
    
    Analyze the attached CSV of government awards to identify:
    1. **DEI Contracts**: Live contracts end date after today with "diversity," "equity," "inclusion," "DEI," "DEIA," or "DEBIA" in `prime_award_base_transaction_description`. These align with the Executive Order targeting DEI waste.
    2. **DOGE Targets**: Live contracts end date after today indicating potential fraud, waste, or abuse per doge.gov/savings—e.g., amounts >$1M, vague descriptions ("support services," "consulting," "training," "management" without specifics), or non-essential spending (e.g., travel, cultural fluff).

    For each:
    - Extract `award_id_piid`, `current_total_value_of_award`, `prime_award_base_transaction_description`, `period_of_performance_current_end_date` and `recipient_name`.
    - Flag if live: end date after today.
    - Summarize the description for each award but keep the keywords in the original text. Make them as short as possible.
    - Double check if the contract is live by using the https://www.fpds.gov/ ezSearch and review all modification to make determine if the contract has been terminated it. E.g. "terminted for convinience", "close out" or updated end date is before today.
    - Output as two JSON lists: `dei_contracts` and `doge_targets`.
    - If a award is flagged for one list (`dei_contracts` OR `doge_targets`) then it should not be added to the other list.

    Rules:
    - Go to https://doge.gov/savings and look at the contract descriptions in the list ot understand the mission criticality. Use the descriptions on the websiteto flag contracts on the provided text.
    - Case-insensitive keyword search.
    - Ignore terminated/expired rows, end date after today.
    - For DOGE, prioritize any amount or vague terms unless clearly mission-critical (e.g., "aircraft maintenance" is fine, "training" alone isn’t).  
    - Make output JSON as compact as possible only including `id`, `amount`, `description`, and `recipient`.

    Example Output:
    {   
    "dei_contracts": [
        {"id": "75P00123P00067", "amount": 500000, "description": "Training", "recipient": "Me, LLC"}
    ],
    "doge_targets": [
        {"id": "SAQMMA15F0999", "amount": 500000, "description": "Training", "recipient": "Me, LLC"}
    ]
    }
    """

ngo_fraud_prompt = """
    I have the following CSV files: 

    Process these files with the following parameters: 
    
    Analyze the attached CSV of government awards to identify:
    1. Live contracts end date after today indicating potential fraud, waste, or abuse per doge.gov/savings—e.g., amounts >$1M, vague descriptions ("support services," "consulting," "training," "management" without specifics), or non-essential spending (e.g., travel, cultural fluff).
    2. Live grants that are giving money to companies or NGOs that are not mission-critical. Specially looks for grant awarded to other countries.
    3. Look into grants that have a high amount of money, 
    
    For each:
    - Extract `award_id_piid`, `total_obligated_amount`, `prime_award_base_transaction_description`, `period_of_performance_current_end_date` and `recipient_name`.
    - Flag if live: end date after today.
    - Summarize the description for each award but keep the keywords in the original text. Make them as short as possible.
    - Double check if the contract is live by using the https://www.fpds.gov/ ezSearch and review all modification to make determine if the contract has been terminated it. E.g. "terminted for convinience", "close out" or updated end date is before today.
    - Output as two JSON lists: `dei_contracts` and `doge_targets`.
    - If a award is flagged for one list (`dei_contracts` OR `doge_targets`) then it should not be added to the other list.

    Rules:
    - Go to https://doge.gov/savings and look at the contract descriptions in the list ot understand the mission criticality. Use the descriptions on the websiteto flag contracts on the provided text.
    - Case-insensitive keyword search.
    - Ignore terminated/expired rows, end date after today.
    - Prioritize any amount or vague terms unless clearly mission-critical (e.g., "aircraft maintenance" is fine, "training" alone isn’t).  
    - Make output JSON as compact as possible including `id`, `amount`, `description`, `recipient` and `recipient_info`.

    Example Output:
    {   
    "dei_contracts": [
    {"id": "75P00123P00067", "amount": 500000, "description": "Training", "recipient": "Me, LLC", "recipient_info": "Company is associated with multiple vague training contracts"}
    ],
    "doge_targets": [
        {"id": "SAQMMA15F0999", "amount": 500000, "description": "Research", "recipient": "Me, LLC", "recipient_info": "NGO owned by a a company or person associated to the Democratic Party.}
    ]
    }
    """
