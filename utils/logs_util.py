import logging
import os
import json
import re
from datetime import datetime
from utils.config_util import platforms, models, tests, LOGS_DIR
from utils.artifacts_util import fetch_performance_data

def parse_azure_pipeline_log(log_content: str):
    """
    Parses Azure pipeline logs to extract errors and specific error types.
    
    Args:
        log_content (str): The content of the Azure pipeline log file
        
    Returns:
        List[Dict]: List of dictionaries containing error information with timestamps
    """
    # Patterns for different types of errors
    timestamp_pattern = r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+Z)"
    ado_error_pattern = fr"{timestamp_pattern} ##\[error\](.*?)(?=\d{{4}}-\d{{2}}-\d{{2}}T|\Z)"
    python_error_patterns = {
        'Traceback': r"Traceback \(most recent call last\):.*?(?=\d{4}-\d{2}-\d{2}T|\Z)",
        'ValueError': r"ValueError:.*?(?=\d{4}-\d{2}-\d{2}T|\Z)",
        'IndexError': r"IndexError:.*?(?=\d{4}-\d{2}-\d{2}T|\Z)",
        'AssertionError': r"AssertionError:.*?(?=\d{4}-\d{2}-\d{2}T|\Z)",
        'AttributeError': r"AttributeError:.*?(?=\d{4}-\d{2}-\d{2}T|\Z)",
        'ImportError': r"ImportError:.*?(?=\d{4}-\d{2}-\d{2}T|\Z)",
        'KeyError': r"KeyError:.*?(?=\d{4}-\d{2}-\d{2}T|\Z)",
        'NameError': r"NameError:.*?(?=\d{4}-\d{2}-\d{2}T|\Z)",
        'MemoryError': r"MemoryError:.*?(?=\d{4}-\d{2}-\d{2}T|\Z)",
        'TypeError': r"TypeError:.*?(?=\d{4}-\d{2}-\d{2}T|\Z)"
    }
    
    errors = []
    
    try:
        # Find Azure DevOps errors
        ado_error_matches = re.finditer(ado_error_pattern, log_content, re.DOTALL)
        for match in ado_error_matches:
            raw_timestamp = match.group(1)
            try:
                truncated_timestamp = raw_timestamp[:26] + "Z" if "." in raw_timestamp else raw_timestamp
                timestamp = datetime.strptime(truncated_timestamp[:-1], "%Y-%m-%dT%H:%M:%S.%f")
                errors.append({
                    "timestamp": timestamp,
                    "message": match.group(2).strip(),
                    "error_type": "ADO Error"
                })
            except ValueError as e:
                logging.error(f"Error parsing timestamp: {raw_timestamp}. Details: {str(e)}")
        
        # Find Python-specific errors
        for error_type, pattern in python_error_patterns.items():
            error_matches = re.finditer(pattern, log_content, re.DOTALL | re.MULTILINE)
            for match in error_matches:
                # Look for timestamp before the error
                timestamp_match = re.search(timestamp_pattern, log_content[:match.start()])
                timestamp = None
                
                if timestamp_match:
                    raw_timestamp = timestamp_match.group(1)
                    try:
                        truncated_timestamp = raw_timestamp[:26] + "Z" if "." in raw_timestamp else raw_timestamp
                        timestamp = datetime.strptime(truncated_timestamp[:-1], "%Y-%m-%dT%H:%M:%S.%f")
                    except ValueError as e:
                        logging.error(f"Error parsing timestamp for {error_type}: {raw_timestamp}. Details: {str(e)}")
                
                errors.append({
                    "timestamp": timestamp,
                    "message": match.group(0).strip(),
                    "error_type": error_type
                })
                
    except Exception as e:
        logging.error(f"An error occurred while parsing the log content: {str(e)}")
    
    # Sort errors by timestamp
    errors.sort(key=lambda x: x["timestamp"] if x["timestamp"] is not None else datetime.max)
    
    logging.info(f"Parsing completed. Found {len(errors)} errors.")
    return errors


def update_error_info(pipeline_data):
    """
    Updates pipeline data with error information from log files.

    Args:
        pipeline_data (dict): The pipeline data to update with error information.

    Returns:
        dict: The updated pipeline data.
    """
    log_files = [f for f in os.listdir(LOGS_DIR) if f.endswith(".txt")]

    try:
        # Process each log file and update the pipeline data with error details
        for log_file in log_files:
            log_path = os.path.join(LOGS_DIR, log_file)
            with open(log_path, "r", encoding='utf-8') as file:
                errors = parse_azure_pipeline_log(file.read())
            for error in errors:
                for platform in pipeline_data:
                    for record in pipeline_data[platform]:
                        if record["id"] == log_file.split('_')[0]:
                            if "Prediction" in record.get("TestcaseName", ""):
                                error_type = 2
                            elif "Evaluation" in record.get("TestcaseName", ""):
                                error_type = 3
                            else:
                                error_type = 1
                            record.update({
                                "ErrorType": error_type,
                                "ErrorMessage": error["message"]
                            })
    except Exception as e:
        logging.error(f"An error occurred while updating error information: {str(e)}")
    
    return pipeline_data

def generate_testcase_data(pipeline_data, metadata, build_id):
    """
    Generates test case data grouped by platform for a given build ID.

    Args:
        pipeline_data (dict): The pipeline data to generate test case data from.
        metadata (dict): The metadata containing repository and trigger information.
        build_id (int): The build ID to associate with the test case data.

    Returns:
        dict: The generated test case data grouped by platform.
    """
    data = {platform: [] for platform in platforms}
    
    try:
        # Populate test case data for each platform, model, and test type
        for platform in platforms:
            for model in models:
                for test in tests:
                    testcase_name = f"{test}_Stage_{platform}." + (f"{test}.{model}" if test == 'Prediction' else f"{test}_{model}.__default")
                    default_record = {
                        "TestcaseName": testcase_name,
                        "Architecture": platform,
                        "PipelineRunID": build_id,
                        "PipelineRunLink": f"https://devicesasg.visualstudio.com/PerceptiveShell/_build/results?buildId={build_id}&view=results",
                        "Status": "Skipped",
                        "TimeStamp": "N/A",
                        "AgentName": "N/A",
                        "ErrorType": "N/A",
                        "ErrorMessage": "N/A",
                        "RepoName": metadata.get("repo_name", "N/A"),
                        "RepoCommit": metadata.get("repo_commit", "N/A"),
                        "RepoBranch": metadata.get("repo_branch", "N/A"),
                        "TriggerType": metadata.get("trigger_type", "N/A"),
                        "TriggeredBy": metadata.get("triggered_by", "N/A"),
                        "Duration": "N/A",
                        "PerformanceMetrics": 'None'
                    }
                    data[platform].append(default_record)

        if pipeline_data:
            # Validate and filter pipeline_data
            valid_records = {
                (platform, record["TestcaseName"]): record
                for platform, records in pipeline_data.items()
                for record in records
                if isinstance(record, dict) and "TestcaseName" in record
            }

            for platform in platforms:
                for record in data[platform]:
                    key = (platform, record["TestcaseName"])
                    if key in valid_records:
                        record.update(valid_records[key])
                        # Fetch performance data if Status is "success" and TestcaseName contains "Evaluation"
                        if record["Status"] == "succeeded" and "Evaluation" in record["TestcaseName"]:
                            performance_data = fetch_performance_data(record["Architecture"], record["TestcaseName"])
                            record["PerformanceMetrics"] = performance_data
                        if isinstance(record["PerformanceMetrics"], dict):
                                record["PerformanceMetrics"] = json.dumps(record["PerformanceMetrics"])
            
        logging.info(f"Test case data generation complete for Build ID: {build_id}.")
    except Exception as e:
        logging.error(f"An error occurred while generating test case data: {str(e)}")
    
    return data
