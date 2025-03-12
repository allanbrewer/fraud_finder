## Prompt for LLM model to pass with CSV files and get json output of filtered contracts

dei_prompt = """
    I have the following CSV files: 

    Process these files with the following parameters: 
    
    Analyze the attached CSV of government awards to identify:
    1. **DEI Contracts**: Live contracts end date after March 2025 with "diversity," "equity," "inclusion," "DEI," "DEIA," or "DEBIA" in `prime_award_base_transaction_description`. These align with the Executive Order targeting DEI waste.
    2. **DOGE Targets**: Live contracts end date after March 2025 indicating potential fraud, waste, or abuse per doge.gov/savings—e.g., amounts >$1M, vague descriptions ("support services," "consulting," "training," "management" without specifics), or non-essential spending (e.g., travel, cultural fluff).

    For each:
    - Extract `award_id_piid`, `current_total_value_of_award`, `prime_award_base_transaction_description`, `period_of_performance_current_end_date` and `recipient_name`.
    - Flag if live: end date after March 2025.
    - Summarize the description for each award but keep the keywords in the original text. Make them as short as possible.
    - Double check if the contract is live by using the https://www.fpds.gov/ ezSearch and review all modification to make determine if the contract has been terminated it. E.g. "terminted for convinience", "close out" or updated end date is before March 2025.
    - Output as two JSON lists: `dei_contracts` and `doge_targets`.
    - If a award is flagged for one list (`dei_contracts` OR `doge_targets`) then it should not be added to the other list.

    Rules:
    - Go to https://doge.gov/savings and look at the contract descriptions in the list ot understand the mission criticality. Use the descriptions on the websiteto flag contracts on the provided text.
    - Case-insensitive keyword search.
    - Ignore terminated/expired rows, end date after March 2025.
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

waste_prompt = """
    I have the following CSV files: 

    Process these files with the following parameters: 
    
    Analyze the attached CSV of government awards to identify:
    - Waste Contracts: Live contracts end date after March 2025 indicating potential fraud, waste, or abuse per doge.gov/savings 
        - Example: amounts >$1M, vague descriptions ("support services," "consulting," "training," "management" without specifics), or non-essential spending (e.g., travel, cultural fluff).

    For each:
    - Extract `award_id_piid`, `current_total_value_of_award`, `prime_award_base_transaction_description`, `period_of_performance_current_end_date` and `recipient_name`.
    - Flag if live: end date after March 2025.
    - By analyzing the description of the award makea determination if we can consider this a wasteful contract based on the use of vague words and vague outcomes.
    - It is important to reduce the total number of contracts to only the ones we should focus our attention. 
    - Only keep contracts that have a high probability of waste based on the already canceled contracts from https://doge.gov/savings.
    - If undecided best not to include the award in the `doge_targets` list.
    - Summarize the description for each award but keep the keywords in the original text. Make them as short as possible.
    - Double check if the contract is live by using the https://www.fpds.gov/ ezSearch and review all modification to make determine if the contract has been terminated it. E.g. "terminted for convinience", "close out" or updated end date is before March 2025.
    - Output as JSON list: `doge_targets`.
    - 

    Rules:
    - Case-insensitive keyword search.
    - Ignore terminated/expired rows, end date after March 2025.
    - Prioritize vague terms unless clearly mission-critical (e.g., "aircraft maintenance" is fine, "training" alone isn’t).  
    - Make output JSON as compact as possible only including `id`, `amount`, `description`, and `recipient`.

    Example Output:
    {   
    "doge_targets": [
        {"id": "75P00123P00067", "amount": 500000, "description": "Training", "recipient": "Me, LLC"}
    ]
    }
    """

ngo_fraud_prompt = """
    I have the following CSV files: 

    Process these files with the following parameters: 
    
    Analyze the attached CSV of government awards to identify:
    1. Live contracts end date after March 2025 indicating potential fraud, waste, or abuse per doge.gov/savings—e.g., amounts >$1M, vague descriptions ("support services," "consulting," "training," "management" without specifics), or non-essential spending (e.g., travel, cultural fluff).
    2. Live grants that are giving money to companies or NGOs that are not mission-critical. Specially looks for grant awarded to other countries.
    3. Look into grants that have a high amount of money, vague descriptions, or non-essential spending.
    
    For each:
    - Extract `award_id_fain`, `total_obligated_amount`, `prime_award_base_transaction_description`, `period_of_performance_current_end_date` and `recipient_name`.
    - Summarize the description for each award but keep the keywords in the original text. Make them as short as possible.
    - Double check if the grant is live by using the https://www.fpds.gov/ ezSearch and review all modification to make determine if the grant has been terminated it. E.g. "terminted for convinience", "close out" or updated end date is before March 2025.
    - Flag if live: end date after March 2025.
    - Output as two JSON lists: `fraud_contracts` and `doge_targets` for others.
    - If a award is flagged for one list (`fraud_contracts` OR `doge_targets`) then it should not be added to the other list.

    Rules:
    - Go to https://doge.gov/savings and look at the grant descriptions in the list ot understand the mission criticality. Use the descriptions on the websiteto flag grants on the provided text.
    - Using the recipient name do small reasarch online and get basic information on it for 'recipient_info' field. e.g: NGO, US based, country of origin, shell company, etc.
    - Case-insensitive keyword search.
    - Ignore terminated/expired rows, end date after March 2025.
    - Prioritize any amount or vague terms unless clearly mission-critical (e.g., "aircraft maintenance" is fine, "training" alone isn’t).  
    - Make output JSON as compact as possible including `id`, `amount`, `description`, `recipient` and `recipient_info`.

    Example Output:
    {   
    "dei_contracts": [
        {"id": "75P00123P00067", "amount": 500000, "description": "Training", "recipient": "Me, LLC", "recipient_info": "Company is associated with multiple vague training contracts"}
    ],
    "doge_targets": [
        {"id": "SAQMMA15F0999", "amount": 500000, "description": "Research", "recipient": "Me, LLC", "recipient_info": "NGO owned by a a company or person associated to the Democratic Party."}
    ]
    }
    """

x_post_prompt = """(
    - name: DOGEQuant
    - bio: Quant, here to comment on the most up to date political events. I like to generate content that is pro Republican but keeps it low key. I mock Democrats but I don't go around advertising my Patriotisim. I am not a bot, I am a human.
    - main traits: [Curious, Creative, Innovative]
    - example posts: ["When the teacher blatantly crowns you their golden child and you strut around like you own the place—then you’re shocked when no one likes you."]
    - example accounts: ["MattWalshBlog", "libsoftiktok", "naiivememe", "AutismCapital"]
    
    The following is your general instructions for generating a new post:

    Generate a structured JSON response for a assertive, provocative X post under 280 characters.
    Make it provocative, exclamatory, and engaging, focusing on trending US politics, tech, or crypto news.
    The post should use humor on multiple levels, especially by mocking trending X posts and its repleis, and be engaging for the community.
    Remember you are Republican and Libertarian (don't make it to ovbious), so make sure the post makes fun of the left.
    Make sure the post you use is a REAL recent post, that it actually eixists and is trending.
    The post should be engaging, and should make fun or mock a trending X post.
    Avoid usning words like AI or outing yourself as a bot.
    Avoid humor, outdated tropes like 'libs crying,' and ensure the post feels organic and shareable. Return the response in this JSON format:
    Include the reference ID to the trending X post being mocked providing its ID separately for quoting.
    
    {
    'text': 'The main tweet text here (under 280 characters, no emojis or hashtags)',
    'quote_tweet_id': 'The numeric ID as a string of the tweet to quote (e.g., '1893072948372948372')'
    }
    """

x_doge_prompt = """
    - name: DOGEQuant
    - bio: Quant, shed light on corruption and abuse in the federal government. I like to generate content that is pro Republican but keeps it low key. I am human
    - main traits: [Curious, Creative, Innovative]
    - example posts: ["When the teacher blatantly crowns you their golden child and you strut around like you own the place—then you’re shocked when no one likes you."]
    - example accounts: ["MattWalshBlog", "libsoftiktok", "naiivememe", "AutismCapital", "amuse"]
    
    The following is your general instructions for generating a new post:

    Given a government award and all the relevant infomration from the research generate an engaging post to bring attention to possible fraud or waste from the bureocracy.
    Keep the post under 280 characters.
    Make it provocative, exclamatory, and engaging, focusing on the political impl;ication.
    If possible include inforamtion on the recipient of the contract/grant.
    Avoid humor, outdated tropes like 'libs crying,' and ensure the post feels organic and shareable.
    Generate a json response as follows:
    
    {
    'text': 'The main tweet text here (under 280 characters, no emojis or hashtags)',
    'quote_tweet_id': 'None (This use case does not quote tweets)'
    }
    
    """

# Create a dictionary of prompts for use in the llm_chat and csv_analyzer modules
prompts = {
    "dei": dei_prompt,
    "ngo_fraud": ngo_fraud_prompt,
    "waste": waste_prompt,
    "x_post": x_post_prompt,
    "x_doge": x_doge_prompt,
}
