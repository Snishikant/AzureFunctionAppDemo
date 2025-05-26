import json
import logging

from database.config import db_connection, DatabaseConnector
from database.constants import WORKLOADS_TABLE_NAME, ihv_dict

# APIs to push data to db
def push_data_to_db(data, build_id):
    """
    Push data to appropriate databases based on platform.
    
    Args:
        data (dict): Dictionary with platform as key and records as values
        build_id (str): The build ID for the pipeline run
    """
    try:
        for platform, records in data.items():
            push_data_to_specific_db(records, platform, build_id)
    finally:
        # Close all database connections when done
        DatabaseConnector.get_instance().close_all_connections()

# Function to push data to IHV-specific PostgreSQL database
def push_data_to_specific_db(records, platform, build_id):
    """
    Push data to an IHV-specific PostgreSQL database.
    
    Args:
        records (list): List of record dictionaries to insert/update
        platform (str): Platform identifier (e.g., 'x64_vitis')
        build_id (str): The build ID for the pipeline run
    """
    # Get the IHV from the platform
    ihv = ihv_dict.get(platform)
    if not ihv:
        logging.error(f"Unknown platform: {platform}. Cannot determine IHV.")
        return
        
    # Use context manager to handle the connection
    with db_connection(ihv) as conn:
        if conn is None:
            logging.error(f"Unable to establish connection for {ihv}.")
            return

        exists = False
        with conn.cursor() as cursor:
            # Check existing records
            check_query = f"""
                SELECT COUNT(*)
                FROM {WORKLOADS_TABLE_NAME}
                WHERE azurepipelineid = %s AND typeofapp = 'ps-evals'
            """
            cursor.execute(check_query, (build_id,))
            exists = cursor.fetchone()[0] > 0

        try:
            with conn.cursor() as cursor:
                for record in records:
                    performance_metrics_json = json.dumps(record["PerformanceMetrics"]) if record["PerformanceMetrics"] else None
                    
                    if exists:
                        # Update existing records
                        update_query = f"""
                            UPDATE {WORKLOADS_TABLE_NAME}
                            SET name = %s,
                                architecture = %s,
                                testresult = %s,
                                resultssummary = jsonb_build_object('ErrorType', %s, 'ErrorMessage', %s),
                                azurepipelinelink = %s,
                                agentpool = %s,
                                timestamp = %s,
                                performancemetrics = %s,
                                miscellaneous = jsonb_build_object('Duration', %s, 'RepoName', %s, 'RepoCommit', %s, 'RepoBranch', %s, 'TriggerType', %s, 'TriggeredBy', %s)
                            WHERE azurepipelineid = %s AND typeofapp = 'ps-evals' AND name = %s
                        """
                        params = (
                            record.get('TestcaseName', 'N/A'),
                            record.get('Architecture', 'N/A'),
                            record.get('Status', 'N/A'),
                            record.get('ErrorType', 'N/A'),
                            record.get('ErrorMessage', 'N/A'),
                            record.get('PipelineRunLink', 'N/A'),
                            record.get('AgentName', 'N/A'),
                            record.get('TimeStamp', 'N/A'),
                            performance_metrics_json,
                            record.get('Duration', 'N/A'),
                            record.get('RepoName', 'N/A'),
                            record.get('RepoCommit', 'N/A'),
                            record.get('RepoBranch', 'N/A'),
                            record.get('TriggerType', 'N/A'),
                            record.get('TriggeredBy', 'N/A'),
                            record.get('PipelineRunID', 'N/A'),  # For WHERE clause
                            record.get('TestcaseName', 'N/A')    # For WHERE clause
                        )
                        cursor.execute(update_query, params)
                    else:
                        # Insert new records
                        insert_query = f"""
                            INSERT INTO {WORKLOADS_TABLE_NAME} (
                                name,
                                architecture,
                                testresult,
                                resultssummary,
                                azurepipelineid,
                                azurepipelinelink,
                                agentpool,
                                typeofapp,
                                timestamp,
                                performancesummary,
                                performancemetrics,
                                miscellaneous
                            )
                            VALUES (
                                %s, %s, %s, jsonb_build_object('ErrorType', %s, 'ErrorMessage', %s), %s, %s, %s, 'ps-evals', %s, NULL, %s,
                                jsonb_build_object('Duration', %s, 'RepoName', %s, 'RepoCommit', %s, 'RepoBranch', %s, 'TriggerType', %s, 'TriggeredBy', %s)
                            )
                        """
                        params = (
                            record.get('TestcaseName', 'N/A'),
                            record.get('Architecture', 'N/A'),
                            record.get('Status', 'N/A'),
                            record.get('ErrorType', 'N/A'),
                            record.get('ErrorMessage', 'N/A'),
                            record.get('PipelineRunID', 'N/A'),
                            record.get('PipelineRunLink', 'N/A'),
                            record.get('AgentName', 'N/A'),
                            record.get('TimeStamp', 'N/A'),
                            performance_metrics_json,
                            record.get('Duration', 'N/A'),
                            record.get('RepoName', 'N/A'),
                            record.get('RepoCommit', 'N/A'),
                            record.get('RepoBranch', 'N/A'),
                            record.get('TriggerType', 'N/A'),
                            record.get('TriggeredBy', 'N/A')
                        )
                        cursor.execute(insert_query, params)
                    
                    conn.commit()
                    logging.info(f"Record for {record.get('TestcaseName', 'N/A')} {'updated' if exists else 'inserted'} successfully.")
                    
        except Exception as e:
            logging.error(f"Error processing data for {ihv}: {str(e)}")
            conn.rollback()  # Rollback any uncommitted transactions