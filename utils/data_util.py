import os
import zipfile
import logging
import json

from utils.config_util import DATA_DIR, LOGS_DIR, ARTIFACTS_DIR
from utils.logs_util import update_error_info, generate_testcase_data
from utils.artifacts_util import process_all_artifacts
from database.push_data import push_data_to_db

def process_data(build_id: str) -> dict:
    """
    Reads pipeline data, updates it with errors, generates test case data, and pushes it to the database.

    Args:
        build_id (str): The build ID to process.

    Returns:
        data (dict): data to be pushed to DB.
    """
    data = {}
    input_file_path = os.path.join(DATA_DIR, f"job_records_{build_id}.json")
    metadata_file_path = os.path.join(DATA_DIR, f"job_records_metadata_{build_id}.json")

    try:
        pipeline_data = []
        if os.path.exists(input_file_path):
            with open(input_file_path, "r") as file:
                pipeline_data = json.load(file)
            if not pipeline_data:
                logging.warning(f"The file {input_file_path} is empty. Proceeding with empty data.")
        else:
            logging.warning(f"File {input_file_path} does not exist. Proceeding with empty pipeline data.")

        # Read metadata from the metadata file
        metadata = {}
        if os.path.exists(metadata_file_path):
            with open(metadata_file_path, "r") as metadata_file:
                metadata = json.load(metadata_file)
            logging.info(f"Metadata: {metadata}")
        else:
            logging.warning(f"Metadata file {metadata_file_path} does not exist. Proceeding without metadata.")

        # Update error information and generate structured test case data
        pipeline_data = update_error_info(pipeline_data)
        data = generate_testcase_data(pipeline_data, metadata, build_id)

        # Save the updated data to a JSON file
        output_file = f"pipeline_logs/jsonDB_{build_id}.json"
        with open(output_file, "w") as file:
            json.dump(data, file, indent=4)
    except Exception as e:
        logging.error(f"An error occurred while processing data: {str(e)}")
    return data

def process_run_data(zip_path: str, build_id: str):
    """
    Process a ZIP package: validate, extract, and route folders for processing.

    Args:
        zip_path (str): Path to the uploaded ZIP file.
        build_id (str): The build ID extracted from the blob name.
    """
    try:
        if not zip_path.endswith(".zip"):
            raise ValueError("Unsupported file format. Expected a .zip file.")

        logging.info(f"Processing ZIP file: {zip_path} for build ID: {build_id}")

        # Ensure DATA_DIR is clean
        if os.path.exists(DATA_DIR):
            logging.info(f"Clearing existing DATA_DIR: {DATA_DIR}")
            import shutil
            shutil.rmtree(DATA_DIR)
        os.makedirs(DATA_DIR, exist_ok=True)

        # Extract the ZIP file into DATA_DIR
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(DATA_DIR)
        logging.info(f"Extracted ZIP to: {DATA_DIR}")

        # Ensure required directories exist after extraction
        if not os.path.isdir(LOGS_DIR):
            raise FileNotFoundError(f"Expected logs directory not found at: {LOGS_DIR}")
        if not os.path.isdir(ARTIFACTS_DIR):
            raise FileNotFoundError(f"Expected artifacts directory not found at: {ARTIFACTS_DIR}")

        # Process and push data
        process_all_artifacts(build_id)
        data = process_data(build_id)
        push_data_to_db(data, build_id)

        logging.info("Run data processing complete.")
    except (ValueError, FileNotFoundError) as e:
        logging.error(f"An error occurred: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"An unexpected error occurred: {str(e)}")
        raise
