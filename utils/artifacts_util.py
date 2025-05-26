import logging
import zipfile
import os
import shutil
import json
from utils.config_util import ARTIFACTS_DIR

def fetch_performance_data(architecture, testcase_name):
    """
    Fetches performance data for a given architecture and test case name by reading from combined JSON files.

    Args:
        architecture (str): The architecture to match (e.g., "arm64_npu").
        testcase_name (str): The name of the test case to match.

    Returns:
        dict: The performance data for the test case.
    """
    try:
        # Check if '.' is present in the testcase_name
        if '.' not in testcase_name:
            logging.warning(f"Invalid testcase_name format: {testcase_name}.")
            return {}       
        # Split the string by periods (.)
        testcase_parts = testcase_name.split('.')

        # Extract the second part and remove the 'Evaluation_' prefix
        model_name = testcase_parts[1].replace("Evaluation_", "")

        # Define the directory containing combined JSON files
        combined_json_dir = os.path.join(os.getcwd(), ARTIFACTS_DIR)
        logging.info(f"Reading performance metrics from: {combined_json_dir}")

        if not os.path.exists(combined_json_dir):
            logging.warning(f"Combined JSON directory does not exist: {combined_json_dir}")
            return {}

        # Iterate through all JSON files in the directory
        for file_name in os.listdir(combined_json_dir):
            if file_name.endswith(".json"):
                # Check if the file name matches the architecture and contains the relevant test case name
                if architecture in file_name and model_name in file_name:
                    # Find matching performance data in combined_data
                    file_path = os.path.join(combined_json_dir, file_name)
                    with open(file_path, 'r', encoding='utf-8') as json_file:
                        combined_data = json.load(json_file)
                        logging.info(f"Reading data from file: {file_path}")
                        return combined_data

        logging.info(f"No matching performance data found for TestcaseName: {testcase_name} and Architecture: {architecture}")
    except Exception as e:
        logging.error(f"An error occurred while fetching performance data: {str(e)}")

    return {}

def process_artifact(artifact_path, artifact_name):
    """
    Processes the downloaded artifact by extracting its contents and performing necessary operations.

    Args:
        artifact_path (str): The path to the downloaded artifact ZIP file.
        artifact_name (str): The name of the artifact being processed.
    """
    # Define the extraction directory
    extraction_dir = os.path.join(os.path.dirname(artifact_path), "extracted_artifact")
    processed_files = set()  # Initialize the set to track processed files

    try:
        # Create the extraction directory if it doesn't exist
        os.makedirs(extraction_dir, exist_ok=True)
        logging.info(f"Created extraction directory: {extraction_dir}")

        # Validate and extract the ZIP file
        if not zipfile.is_zipfile(artifact_path):
            logging.error(f"Invalid ZIP file: {artifact_path}")
            return

        with zipfile.ZipFile(artifact_path, 'r') as zip_ref:
            zip_ref.extractall(extraction_dir)
            logging.info(f"Extracted ZIP file: {artifact_path} to {extraction_dir}")

        # Process the extracted files
        for root, dirs, files in os.walk(extraction_dir):
            for file in files:
                file_path = os.path.join(root, file)
                logging.info(f"Processing file: {file_path}")
                combined_json = process_file(file_path, artifact_name, processed_files)
                write_combined_json_to_file(combined_json, artifact_name)

        logging.info(f"Successfully processed the artifact: {artifact_path}")

    except Exception as e:
        logging.error(f"An error occurred while processing the artifact: {str(e)}")

    finally:
        # Cleanup the extraction directory
        if os.path.exists(extraction_dir):
            shutil.rmtree(extraction_dir)
            logging.info(f"Cleaned up extraction directory: {extraction_dir}")

def delete_artifact(artifact_path):
    if os.path.exists(artifact_path):
        if os.path.isdir(artifact_path):
            shutil.rmtree(artifact_path)
            logging.info(f"Deleted directory: {artifact_path}")
        else:
            os.remove(artifact_path)
            logging.info(f"Deleted file: {artifact_path}")
    else:
        logging.warning(f"Artifact not found: {artifact_path}")

def write_combined_json_to_file(combined_json, artifact_name):
    if combined_json:
        output_dir = os.path.join(os.getcwd(), ARTIFACTS_DIR)
        os.makedirs(output_dir, exist_ok=True)
        output_file_path = os.path.join(output_dir, f"{artifact_name}.json")
        # Write the combined JSON data to the file
        with open(output_file_path, 'w', encoding='utf-8') as outfile:
            json.dump(combined_json, outfile, indent=4)
        logging.info(f"Combined JSON file created: {output_file_path}")

def process_file(file_path, artifact_name, processed_files):
    """
    Processes an individual file and combines all JSON files into a single JSON file.

    Args:
        file_path (str): The path to the file or directory to be processed.
        artifact_name (str): The name of the artifact for the output JSON file.
    """
    logging.info(f"Processing file: {file_path}")

    # Check if the file has already been processed
    if file_path in processed_files:
        logging.info(f"Skipping already processed file: {file_path}")
        return []  # Return an empty list to indicate no new data

    combined_json = []  # Initialize an empty list to hold the combined JSON data

    # Mark the file as processed
    processed_files.add(file_path)

    if file_path.endswith('.zip'):
        # If the file is a ZIP file, extract it and process its contents
        extraction_dir = os.path.join(os.path.dirname(file_path), os.path.splitext(os.path.basename(file_path))[0])
        os.makedirs(extraction_dir, exist_ok=True)
        with zipfile.ZipFile(file_path, 'r') as zip_ref:
            zip_ref.extractall(extraction_dir)
        logging.info(f"Extracted ZIP file: {file_path} to {extraction_dir}")

        # Recursively process the extracted files
        for root, dirs, files in os.walk(extraction_dir):
            for file in files:
                combined_json += process_file(os.path.join(root, file), artifact_name, processed_files)
            for dir in dirs:
                combined_json += process_file(os.path.join(root, dir), artifact_name, processed_files)

    elif file_path.endswith('.json'):
        if "embeddings" in artifact_name:
            if 'alpha' in os.path.basename(file_path):
                with open(file_path, 'r', encoding='utf-8') as file:
                    content = json.load(file)
                    file_name = os.path.splitext(os.path.basename(file_path))[0]
                    combined_json.append({file_name: content})
                    #combined_json.append(content)
                logging.info(f"Added content from JSON file: {file_path}")
        # If the file is a JSON file, read and add its contents to the combined_json list
        else:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = json.load(file)
                file_name = os.path.splitext(os.path.basename(file_path))[0]
                combined_json.append({file_name: content})
                #combined_json.append(content)
                logging.info(f"Added content from JSON file: {file_path}")

    return combined_json

"""
#Example for local usage and testing
# Configuration
organization = 'devicesasg'
project = 'PerceptiveShell'
build_id = '163518'
pat_token = ''  # Copy Personal Access Token (PAT) with appropriate permissions
# Encode the PAT token
encoded_pat = base64.b64encode(f":{pat_token}".encode()).decode()
def get_build_artifacts():
    url = f"https://{organization}.visualstudio.com/{project}/_apis/build/builds/{build_id}/artifacts?api-version=7.1"
    print(url)
    
    # Prepare headers with the encoded PAT token for authorization
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Basic {encoded_pat}'
    }
    
    # Make the HTTP request to get artifacts
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        artifacts = response.json().get('value', [])
        return artifacts
    else:
        logging.error(f"Failed to get artifacts: {response.status_code} - {response.text}")
        return []

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logging.info('Processing Azure Pipeline artifacts...')
    artifacts = get_build_artifacts()
    # Process all the artifacts
    process_artifacts(artifacts)""
"""