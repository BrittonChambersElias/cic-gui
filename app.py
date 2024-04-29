# refresh filters after single row updates

import sys
import subprocess
import pkg_resources

def install_missing_packages():
    # List of third-party packages that are not part of the Python standard library
    required = {'flask', 'pandas', 'werkzeug', 'filelock', 'numpy'}
    installed = {pkg.key for pkg in pkg_resources.working_set}
    missing = required - installed

    if missing:
        print("Missing packages:", missing)
        python = sys.executable
        try:
            subprocess.check_call([python, '-m', 'pip', 'install', *missing], stdout=subprocess.DEVNULL)
            print("All missing packages were successfully installed.")
        except subprocess.CalledProcessError as e:
            print(f"An error occurred while installing packages: {e}")
            sys.exit(1)

# Call the function to check and install missing packages
install_missing_packages()


from flask import Flask, render_template, request, redirect, url_for, session, send_file, jsonify, after_this_request
import pandas as pd
import os
from werkzeug.utils import secure_filename
import json
import uuid
import shutil
from datetime import datetime
from filelock import Timeout, FileLock
import io

# local imports
from key_generator import secret_key
from df_builder import extract_thresholds, extract_failure_reasons, reconstruct_thresholds, reconstruct_failure_reasons, reintegrate_full_structure


app = Flask(__name__)
app.secret_key = secret_key  # Necessary for session management

# Ensure that the 'uploads' folder exists
UPLOAD_FOLDER = 'uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def add_unique_identifiers(df):
    if 'uid' not in df.columns:
        # Generate a unique identifier for each row and add it as a new column
        df['uid'] = [str(uuid.uuid4()) for _ in range(len(df))]
    return df

def dataframe_to_html_with_uids(df):
    # Create a new DataFrame with 'uid' as the first column
    df = df[['uid'] + [col for col in df.columns if col != 'uid']]
    
    # Start generating the HTML table string
    html = '<table id="myTable" class="display dataTable"><thead><tr>'
    # Headers for actual data columns
    for col in df.columns:
        html += f'<th>{col}</th>'
    # Additional header for the select button
    html += '<th>SelectRow</th>'
    html += '</tr></thead><tbody>'
    

    for index, row in df.iterrows():
        html += f'<tr data-uid="{row["uid"]}">'
        for col in df.columns:
            html += f'<td data-columnName="{col}">{row[col]}</td>'
        html += '<td><button class="selectRowButton">Select</button></td>'
        html += '</tr>'
    
    
    return html

def apply_filters(df, selected_filters):
    for column, values in selected_filters.items():
        # Skip filtering for this column if 'All' is selected
        if 'All' in values:
            continue
        # Filter DataFrame to include rows where the column value matches any of the selected values
        df = df[df[column].isin(values)]
    return df

def validate_filters(selected_filters, valid_combinations):
    for combo in valid_combinations:
        match = True
        for k, selected_values in selected_filters.items():
            combo_value = combo.get(k, None)
            # Adjust comparison logic here
            if not combo_value in selected_values and 'All' not in selected_values:
                match = False
                break
        if match:
            return True, ""
    return False, "The selected filter combination is invalid."

def validate_combinations(combinations):
    return [combo for combo in combinations if all(value not in ['New Grade', 'New Surface', 'New Defect'] for value in combo.values())]

def load_valid_combinations(data_type):
    uid = session.get('file_uid')
    if data_type == 'Thresholds':
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'thresholds_valid_combinations_{uid}.json')
    elif data_type == 'Failure Reasons':
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], f'failure_reasons_valid_combinations_{uid}.json')
    else:
        return []

    with open(file_path, 'r') as file:
        return json.load(file)
    
def update_valid_combinations(new_row, data_type):
    uid = session.get('file_uid')
    normalized_data_type = data_type.replace(" ", "_").lower()  # Replace spaces with underscores and make lowercase
    file_name = f'{normalized_data_type}_valid_combinations_{uid}.json'
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)

    if not os.path.exists(file_path):
        valid_combinations = []
    else:
        with open(file_path, 'r') as file:
            valid_combinations = json.load(file)

    # new_row is a dictionary of the new row's data
    # checks if an exact combination exists, you might adjust based on your needs
    if not any(new_row == combo for combo in valid_combinations):
        valid_combinations.append(new_row)

    with open(file_path, 'w') as file:
        json.dump(valid_combinations, file)


@app.route('/add_row', methods=['POST'])
def add_row():
    rows = request.get_json()  # Extract the array of new rows from the AJAX request
    print("Received rows:", rows)

    if not rows:  # Early return if no data is provided
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400

    data_type = rows[0].get('data_type', 'Thresholds')  # Default to 'Thresholds' if not provided

    # Map 'data_type' to the correct file path
    df_path = {
        'Thresholds': session.get('thresholds_path'),
        'Failure Reasons': session.get('failure_reasons_path')
    }.get(data_type, None)

    if not df_path:  # Early return if data_type is invalid
        return jsonify({'status': 'error', 'message': 'Invalid data type'}), 400

    df = pd.read_csv(df_path)  # Load the DataFrame

    for row in rows:
        # Create a new row ensuring only the columns that exist in df are included
        new_row = {col: row.get(col, 'NaN') for col in df.columns if col in row}
        new_row['uid'] = str(uuid.uuid4())  # Add a unique identifier for the new row
        df = df.append(new_row, ignore_index=True)
        print("New row:", new_row)

        update_valid_combinations(new_row, data_type)  # Update valid combinations

    df.to_csv(df_path, index=False)  # Save the updated DataFrame

    return jsonify({'status': 'success', 'message': f'{len(rows)} rows added successfully'})


@app.route('/add_individual_row', methods=['POST'])
def add_individual_row():
    data = request.get_json()
    print("Received data:", data)

    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400

    data_type = data.get('data_type', 'Thresholds')
    position = data.get('position', 'end')
    referenceUid = data.get('referenceUid', None)

    df_path = {
        'Thresholds': session.get('thresholds_path'),
        'Failure Reasons': session.get('failure_reasons_path')
    }.get(data_type, None)

    if not df_path:
        return jsonify({'status': 'error', 'message': 'Invalid data type'}), 400

    df = pd.read_csv(df_path)
    new_row = {col: data.get(col, 'NaN') for col in df.columns if col in data}
    new_row['uid'] = str(uuid.uuid4())  # Ensure a unique identifier is assigned

    if referenceUid and position in ['above', 'below']:
        reference_index = df[df['uid'] == referenceUid].index.tolist()
        if reference_index:
            insert_index = reference_index[0] + (1 if position == 'below' else 0)
            df = pd.concat([df.iloc[:insert_index], pd.DataFrame([new_row]), df.iloc[insert_index:]]).reset_index(drop=True)
        else:
            return jsonify({'status': 'error', 'message': 'Reference UID not found'}), 404
    else:
        df = df.append(new_row, ignore_index=True)

    df.to_csv(df_path, index=False)

    return jsonify({'status': 'success', 'message': 'Row added successfully', 'newUid': new_row['uid']})





@app.route('/delete_rows', methods=['POST'])
def delete_rows():
    data = request.get_json()
    uids = data.get('uids')  # Expecting an array of UIDs
    if not uids:
        return jsonify({'status': 'error', 'message': 'UIDs not provided'}), 400

    data_type = data.get('data_type', 'Thresholds')
    df_path = {
        'Thresholds': session.get('thresholds_path'),
        'Failure Reasons': session.get('failure_reasons_path')
    }.get(data_type, None)

    if not df_path:
        return jsonify({'status': 'error', 'message': 'Invalid data type'}), 400

    df = pd.read_csv(df_path)
    initial_count = len(df)
    df = df[~df['uid'].isin(uids)]  # Remove the rows with the given UIDs
    df.to_csv(df_path, index=False)  # Save the updated DataFrame

     

    deleted_count = initial_count - len(df)
    return jsonify({'status': 'success', 'message': f'{deleted_count} row(s) deleted successfully'})



def update_valid_combinations(new_row, data_type):
    uid = session.get('file_uid')
    normalized_data_type = data_type.replace(" ", "_").lower()
    file_name = f'{normalized_data_type}_valid_combinations_{uid}.json'
    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file_name)

    if not os.path.exists(file_path):
        valid_combinations = []
    else:
        with open(file_path, 'r') as file:
            valid_combinations = json.load(file)

    # Ensure that the new_row being compared is the updated row and not the placeholder
    new_combination = {k: v for k, v in new_row.items() if v != 'New ' + k}  # Filter out placeholder values

    # Check if an exact combination exists, adjust based on your needs
    if not any(new_combination == combo for combo in valid_combinations):
        valid_combinations.append(new_combination)

    with open(file_path, 'w') as file:
        json.dump(valid_combinations, file)

    print("Updated combinations:", valid_combinations)

        
def clean_upload_folder(uid):
    folder = 'uploads'
    uid_suffix = f"_{uid}"  # Updated: removed the dot to generalize the suffix check
    uid_prefix = f"{uid}_"  # Prefix check remains the same
    
    for filename in os.listdir(folder):

        # Check if filename contains the UID as a suffix before a file extension or starts with it
        if (filename.startswith(uid_prefix) or 
            any(filename.endswith(suffix) for suffix in [f"{uid_suffix}.csv", f"{uid_suffix}.json", f"{uid_suffix}.csv.lock"])):
            file_path = os.path.join(folder, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
            except Exception as e:
                print(f'Failed to delete {file_path}. Reason: {e}')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files['file']
    if file:
        uid = str(uuid.uuid4())
        original_filename = secure_filename(file.filename)
        filename = f"{uid}_{original_filename}"
        #filename = secure_filename(file.filename)
        filename = f"{uid}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        threshold_combinations_path = os.path.join(app.config['UPLOAD_FOLDER'], f'thresholds_valid_combinations_{uid}.json')
        failure_reason_combinations_path = os.path.join(app.config['UPLOAD_FOLDER'], f'failure_reasons_valid_combinations_{uid}.json')
        file.save(filepath)

        # Store the original filename in the session
        session['original_filename'] = original_filename

        # Store the filepath in session for later use
        session['filepath'] = filepath

        # Store the UID in the session or a database as needed
        session['file_uid'] = uid
        
        # Load JSON data
        with open(filepath) as f:
            data = json.load(f)
        
        
        # Convert JSON data to data frames
        thresholds_df = extract_thresholds(data)
        thresholds_df = add_unique_identifiers(thresholds_df)
        failure_reasons_df = extract_failure_reasons(data)
        failure_reasons_df = add_unique_identifiers(failure_reasons_df)

        # Generate valid combinations for each DataFrame
        threshold_valid_combinations = thresholds_df.drop_duplicates(subset=['Grade', 'Surface', 'Defect Type', 'Defect']).to_dict('records')
        failure_reason_valid_combinations = failure_reasons_df.drop_duplicates(subset=['Grade', 'Category', 'Defect', 'Surface']).to_dict('records')
        
                # Convert dictionaries to JSON and save
        with open(threshold_combinations_path, 'w') as file:
            json.dump(threshold_valid_combinations, file)
        
        with open(failure_reason_combinations_path, 'w') as file:
            json.dump(failure_reason_valid_combinations, file)


        # Save data frames to CSV files
        thresholds_path = os.path.join(app.config['UPLOAD_FOLDER'], f'thresholds_{uid}.csv')
        failure_reasons_path = os.path.join(app.config['UPLOAD_FOLDER'], f'failure_reasons_{uid}.csv')
        thresholds_df.to_csv(thresholds_path, index=False)
        failure_reasons_df.to_csv(failure_reasons_path, index=False)
        
        # Store references in session
        session['thresholds_path'] = thresholds_path
        session['failure_reasons_path'] = failure_reasons_path

        # Store these combinations in the session or another suitable place
        session['thresholds_combinations_path'] = threshold_combinations_path
        session['failure_reasons_combinations_path'] = failure_reason_combinations_path

        # Print statements to confirm path was saved in session
        print("File path set in session:", session.get('filepath'))
        print("Thresholds path set in session:", session.get('thresholds_path'))
        print("Failure reasons path set in session:", session.get('failure_reasons_path'))
        
        return redirect(url_for('display_data'))
    
    return redirect(url_for('index'))


@app.route('/display', methods=['GET', 'POST'])
def display_data():
    data_type = 'Thresholds'  # Default data type
    selected_filters = {}  # Default to no filters

    # Define the filter options for each data type
    filter_options = {
        'Thresholds': ['Grade', 'Surface', 'Defect Type', 'Defect', 'All'],
        'Failure Reasons': ['Grade', 'Category', 'Defect', 'Surface', 'All']
    }

    if request.method == 'POST':
        json_data = request.get_json()
        print("Received JSON Data:", json_data)
        data_type = json_data.get('data_type', 'Thresholds')
        selected_filters = json_data.get('filters', {})  # Assume filters is a dict

        valid_combinations = load_valid_combinations(data_type)

        # Perform validation using the appropriate valid_combinations
        isValid, errorMessage = validate_filters(selected_filters, valid_combinations)
        print("isValid:", isValid)
        print("errorMessage:", errorMessage)
        if not isValid:
            return jsonify({'isValid': False, 'errorMessage': errorMessage})
        
        print("Selected Filters: in request.method", selected_filters)
        

    # Common logic for loading and filtering the data frame
    df_path = session.get('thresholds_path')if data_type == 'Thresholds' else session.get('failure_reasons_path')
    if not df_path:
        return "<p>Error loading data. Please upload the file again.</p>", 500
    
    if df_path:
        df = pd.read_csv(df_path)
        df = apply_filters(df, selected_filters)  # Apply filters to the DataFrame
        print("Selected Filters: in df_path", selected_filters)
        table_html = dataframe_to_html_with_uids(df)

        # Prepare filter values for the current data type
        actual_filter_options = [option for option in filter_options[data_type] if option != 'All']

        # Initialize filter_values with empty lists for each option to ensure structure consistency
        filter_values = {option: [] for option in actual_filter_options}

        # Populate filter_values with unique values from the DataFrame
        for option in actual_filter_options:
            if option in df:
                filter_values[option] = df[option].dropna().unique().tolist()

        # Prepare filter values for the current data type
        print("Filter values:", filter_values)
        print("Filter options:", filter_options[data_type])
        if request.method == 'POST' and request.is_json:
            return jsonify({
                'html': table_html,
                'data_type': data_type,
                'filterOptions': filter_options[data_type],
                'filterValues': filter_values
            })
        else:
            # For initial page load, render the full page
            # Pass the default or current data type, its filter options, and values to the template
            return render_template('display.html', table=table_html, data_type=data_type, filter_options=filter_options[data_type], filter_values=filter_values)
    else:
        return "<p>Error loading data. Please upload the file again.</p>", 500

def perform_update(row_uid, column_name, new_value, data_type):
    if data_type == 'Thresholds':
        df_path = session.get('thresholds_path')
    elif data_type == 'Failure Reasons':
        df_path = session.get('failure_reasons_path')
    else:
        raise ValueError('Invalid data type')

    lock_path = df_path + ".lock"
    lock = FileLock(lock_path, timeout=10)
    with lock.acquire(timeout=10):
        df = pd.read_csv(df_path)
        row_index = df.index[df['uid'] == row_uid].tolist()
        if not row_index:
            raise ValueError('Row UID not found')

        df.loc[row_index[0], column_name] = new_value
        df.to_csv(df_path, index=False)
        # Ensure update_valid_combinations is thread-safe if necessary
        update_valid_combinations({'rowUid': row_uid, 'columnName': column_name, 'newValue': new_value, 'dataType': data_type}, data_type)

@app.route('/update_cell', methods=['POST'])
def update_cell():
    data = request.get_json()
    try:
        perform_update(data['rowUid'], data['columnName'], data['newValue'], data['data_type'])
        return jsonify({'status': 'success', 'message': 'Cell updated successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400
    
@app.route('/batch_update_cells', methods=['POST'])
def batch_update_cells():
    updates = request.get_json()
    try:
        for update in updates:
            perform_update(update['rowUid'], update['columnName'], update['newValue'], update['dataType'])
        return jsonify({'status': 'success', 'message': 'Batch update completed successfully'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
     
@app.route('/export', methods=['GET'])
def export_data():
    # Format the timestamp
    timestamp = datetime.now().strftime('%Y%m%d_%H%M')


    try:
        # Retrieve UID and file paths from session
        uid = session.get('file_uid')
        print("Session UID:", uid)
        if not uid:
            raise FileNotFoundError("Session UID not found.")
        # Retrieve file paths from session
        original_filename = session.get('original_filename')
        if not original_filename:
            raise FileNotFoundError("Original filename not found in session.")
        filepath = session.get('filepath')
        thresholds_csv_path = session.get('thresholds_path')
        failure_reasons_csv_path = session.get('failure_reasons_path')

        if not filepath or not thresholds_csv_path or not failure_reasons_csv_path:
            raise FileNotFoundError("Required file path(s) not found in session.")

        # Load the original JSON structure
        with open(filepath, "r") as file:
            original_data = json.load(file)

        # Initialize an empty dictionary for reconstructed data
        reconstructed_cosmetic_data = {}

        # Call reconstruction functions with proper arguments
        reconstructed_cosmetic_data = reconstruct_thresholds(reconstructed_cosmetic_data, thresholds_csv_path)
        reconstructed_cosmetic_data = reconstruct_failure_reasons(reconstructed_cosmetic_data, failure_reasons_csv_path)

        # Reintegrate and save the full structure
        reintegrated_data = reintegrate_full_structure(original_data, reconstructed_cosmetic_data)
        
        # Ensure reintegrated_data is not null and has the expected structure
        if not reintegrated_data:
            raise ValueError("Reintegrated data is null or incorrectly structured.")


        # Create an in-memory file
        json_output = io.BytesIO()
        json_output.write(json.dumps(reintegrated_data, indent=4).encode('utf-8'))
        json_output.seek(0)  # Rewind the file to start

        # Create a file name for the download
        download_filename = f"{timestamp}_{original_filename}"
        
        # After successful export, clean the upload folder
        @after_this_request
        def cleanup(response):
            clean_upload_folder(uid)
            return response
        

        return send_file(json_output, as_attachment=True, download_name=download_filename, mimetype='application/json')
        
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)