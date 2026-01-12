import re

def extract_currency_value(text_value):
    """
    Forensic Cleaner: Extracts the actual float value from a currency string.
    Handles '$105,000', '$105k', '105,000.00', and returns 105000.0
    """
    if not text_value or not isinstance(text_value, str):
        return 0.0
    
    # 1. Remove currency symbols and whitespace
    clean_text = text_value.replace('$', '').replace(',', '').strip()
    
    # 2. Handle "k/m" suffixes (e.g. "$105k") common in AI output
    multiplier = 1.0
    if clean_text.lower().endswith('k'):
        multiplier = 1000.0
        clean_text = clean_text[:-1]
    elif clean_text.lower().endswith('m'):
        multiplier = 1000000.0
        clean_text = clean_text[:-1]

    # 3. Extract the first valid float number found
    try:
        # Regex to find standard float/integer patterns
        match = re.search(r"[-+]?\d*\.\d+|\d+", clean_text)
        if match:
            return float(match.group()) * multiplier
        return 0.0
    except Exception as e:
        print(f"Parsing Error on value '{text_value}': {e}")
        return 0.0

# --- UPDATED CALCULATION LOOP ---
# Replace your existing summation loop with this logic:

def calculate_total_savings(ai_json_data):
    total_savings = 0.0
    
    # Iterate through each product in the AI response
    for product_name, data in ai_json_data.items():
        # Iterate through the 3 Forensic Drivers: Efficiency, Risk, Strategic
        for driver in ['Efficiency', 'Risk', 'Strategic']:
            if driver in data:
                # OLD BROKEN WAY: parsing "Basis of Calculation"
                # basis_text = data[driver].get('basis', '')
                # val = regex_math(basis_text) <--- BUG SOURCE
                
                # NEW ROBUST WAY: Trust the Impact Column
                impact_text = data[driver].get('Annual Impact', '0')
                val = extract_currency_value(impact_text)
                
                total_savings += val
                
    return total_savings
