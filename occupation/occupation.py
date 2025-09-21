import json

# ------------------------------
# Load input occupations
# ------------------------------
with open("occupation.json", "r") as f:
    input_data = json.load(f)

input_occupations = input_data.get("Occupation", [])

# ------------------------------
# Load schemes mapping
# ------------------------------
with open("scheme.json", "r") as f:
    scheme_data = json.load(f)

# ------------------------------
# Map occupations to schemes
# ------------------------------
def map_occupations_to_schemes(input_occupations, scheme_data):
    result = {}
    for occ in input_occupations:
        # Case-insensitive matching
        matched_key = next((k for k in scheme_data if k.lower() == occ.lower()), None)
        if matched_key:
            result[occ] = scheme_data[matched_key]
        else:
            result[occ] = ["No schemes found for this occupation."]
    return result

# Generate output
occupation_to_schemes = map_occupations_to_schemes(input_occupations, scheme_data)

# ------------------------------
# Save output to JSON file
# ------------------------------
with open("output_schemes.json", "w") as f:
    json.dump(occupation_to_schemes, f, indent=4)

print("Output written to 'output_schemes.json'")
