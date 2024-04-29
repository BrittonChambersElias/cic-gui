import json
import pandas as pd
import numpy as np

def extract_thresholds(data):
    extracted_info = []
    
    # Assuming 'data' is the full JSON structure loaded from the file
    cosmetic_data = data.get('test_overrides', {}).get('COSMETIC', {})

    # Now extract information for each grade in 'COSMETIC'
    for grade, grade_info in cosmetic_data.items():
        thresholds = grade_info.get('thresholds', {})
        # Iterate through the thresholds data
        for surface, defects in thresholds.items():
            for defect_type, criteria in defects.items():
                for defect, measurements in criteria.items():
                    data_dict = {
                        'Grade': grade,
                        'Surface': surface,
                        'Defect Type': defect_type,
                        'Defect': defect,
                        'Min Width': measurements.get('min_width', ''),
                        'Max Width': measurements.get('max_width', ''),  # Added 'Max Width' for completeness
                        'Min Length': measurements.get('min_length', ''),
                        'Max Length': measurements.get('max_length', ''),  # Added 'Max Length' for completeness
                        'Min Contrast': measurements.get('min_contrast', ''),
                        'Min Area Pixel': measurements.get('min_area_pixel', '')
                    }
                    extracted_info.append(data_dict)
    return pd.DataFrame(extracted_info)

    
def extract_failure_reasons(data):
    extracted_info = []

    # Assuming 'data' is the full JSON structure loaded from the file
    cosmetic_data = data.get('test_overrides', {}).get('COSMETIC', {})

    # Now extract information for each grade in 'COSMETIC'
    for grade, grade_info in cosmetic_data.items():
        failure_reasons = grade_info.get('failure_reasons', {})
        # Iterate through the failure reasons data
        for category, details in failure_reasons.items():
            code = details.get("code", "")
            hierarchy = details.get("hierarchy", "")
            for failure in details.get("failure_reason", []):
                num = failure.get("num", "")
                defects = failure.get("defects", [])
                surfaces = failure.get("surfaces", {})
                for defect in defects:
                    for surface, surface_detail in surfaces.items():
                        # Check if surface_detail is a list or 'all'
                        if isinstance(surface_detail, list):
                            surface_values = surface_detail
                        else:
                            surface_values = [surface_detail]

                        extracted_info.append({
                            "Grade": grade,
                            "Category": category,
                            "Code": code,
                            "Hierarchy": hierarchy,
                            "Num": num,
                            "Defect": defect,
                            "Surface": surface,
                            "Surface Detail": surface_values  # Now a list, for consistent data structure
                        })

    return pd.DataFrame(extracted_info)



# # Function to reconstruct the thresholds data after editing the values
def reconstruct_thresholds(reconstructed_data, csv_path):
    df_defects = pd.read_csv(csv_path)
    for index, row in df_defects.iterrows():
        grade = row['Grade']
        surface = row['Surface']
        defect_type = row['Defect Type']
        defect = row['Defect']

        # Initialize measurements directly from the row, consider empty strings as None
        measurements = {
            'min_width': None if pd.isna(row['Min Width']) or row['Min Width'] == '' else row['Min Width'],
            'max_width': None if pd.isna(row['Max Width']) or row['Max Width'] == '' else row['Max Width'],
            'min_length': None if pd.isna(row['Min Length']) or row['Min Length'] == '' else row['Min Length'],
            'max_length': None if pd.isna(row['Max Length']) or row['Max Length'] == '' else row['Max Length'],
            'min_contrast': None if pd.isna(row['Min Contrast']) or row['Min Contrast'] == '' else row['Min Contrast'],
            'min_area_pixel': None if pd.isna(row['Min Area Pixel']) or row['Min Area Pixel'] == '' else row['Min Area Pixel']
        }

        # Filter out None values
        #measurements = {k: v for k, v in measurements.items() if v is not None}

        # Check if all measurements are None (which would have been NaN in the original CSV)
        if all(value is None for value in measurements.values()):
            measurements = {} 

        if grade not in reconstructed_data:
            reconstructed_data[grade] = {'thresholds': {}}
        if surface not in reconstructed_data[grade]['thresholds']:
            reconstructed_data[grade]['thresholds'][surface] = {}
        if defect_type not in reconstructed_data[grade]['thresholds'][surface]:
            reconstructed_data[grade]['thresholds'][surface][defect_type] = {}

        # Only add the defect if measurements are not empty
        if measurements:
            reconstructed_data[grade]['thresholds'][surface][defect_type][defect] = measurements
        else:
            # If measurements are empty and you still want to keep the defect key with an empty dict
            reconstructed_data[grade]['thresholds'][surface][defect_type][defect] = {}

    return reconstructed_data
        
# # Function to reconstruct the failure reasons data after editing the values
def reconstruct_failure_reasons(reconstructed_data, csv_path):
    df_failure_reasons = pd.read_csv(csv_path)
    for index, row in df_failure_reasons.iterrows():
        grade = row['Grade']
        category = row['Category']
        
        defects = [defect.strip() for defect in row["Defect"].split(",")]

        # Adjusted handling for 'Num' to be None if it's NaN or empty
        num = None if pd.isna(row["Num"]) else int(row["Num"])

        hierarchy = None if pd.isna(row["Hierarchy"]) else int(row["Hierarchy"])

        # This is the part that needs adjustment
        # 'Surface' column contains the key, e.g., 'B'
        # 'Surface Detail' column should contain the list as a JSON string, e.g., '[10, 11, 12, 13, 15]'
        surface_identifier = row["Surface"]
        surface_detail_raw = row["Surface Detail"]
        # Initialize an empty dictionary for surfaces
        surface_detail = {}

        # Normalize the surface detail handling for both edited and unedited rows
        if pd.isna(surface_detail_raw) or surface_detail_raw.strip() == '':
            surface_detail[surface_identifier] = None
        else:
            surface_detail_raw = surface_detail_raw.strip()
            if surface_detail_raw.lower() == 'all':
                surface_detail[surface_identifier] = "all"
            else:
                try:
                    surface_numbers = json.loads(surface_detail_raw.replace("'", "\""))
                    if isinstance(surface_numbers, list):
                        surface_detail[surface_identifier] = surface_numbers
                    else:
                        # This clause helps ensure single numbers are treated as a list
                        surface_detail[surface_identifier] = [surface_numbers] if isinstance(surface_numbers, int) else surface_numbers
                except json.JSONDecodeError:
                    # Log error for debugging
                    print(f"Error parsing surface detail for {surface_identifier}: {surface_detail_raw}")
                    surface_detail[surface_identifier] = None

        
        failure_reason_detail = {
            "num": num,  # Updated to use the adjusted 'num'
            "defects": defects,
            "surfaces": surface_detail
        }

        # Ensure the grade exists
        if grade not in reconstructed_data:
            reconstructed_data[grade] = {"thresholds": {}, "failure_reasons": {}}

        # Ensure the category under failure_reasons exists
        if "failure_reasons" not in reconstructed_data[grade]:
            reconstructed_data[grade]["failure_reasons"] = {}

        if category not in reconstructed_data[grade]["failure_reasons"]:
            reconstructed_data[grade]["failure_reasons"][category] = {
                "code": row["Code"] if pd.notna(row["Code"]) else None,  # Assuming 'Code' column exists and has been properly populated
                "hierarchy": hierarchy,  # Assuming 'Hierarchy' column exists and has been properly populated
                "failure_reason": []
            }

        # Now that we've ensured all parts of the structure exist, append the failure reason detail
        reconstructed_data[grade]["failure_reasons"][category]["failure_reason"].append(failure_reason_detail)

    return reconstructed_data
    

def reintegrate_full_structure(original_data, reconstructed_cosmetic_data):
    original_data["test_overrides"]["COSMETIC"] = reconstructed_cosmetic_data
    return original_data


