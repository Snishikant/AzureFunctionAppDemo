import os
import logging
import tempfile

import azure.functions as func
from utils.data_util import process_run_data
from utils.config_util import ZIP_SUFFIX

# Initialize the FunctionApp
app = func.FunctionApp()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

CONTAINER_NAME = os.getenv('EVALS_CONTAINER_NAME', 'psevals-data')
# Note: The StorageConnection line has been removed

@app.blob_trigger(
    name="packageTrigger",
    path=f"{CONTAINER_NAME}/{{blob_name}}",
    connection="AzureWebJobsStorage"
)
def package_blob_trigger(blob: func.InputStream):
    """
    Triggered when a ZIP package is uploaded to the specified container.
    Extracts build_id from the blob name and calls process_run_data.
    """
    blob_name = os.path.basename(blob.name)
    logging.info(f"Received blob: {blob_name} (size: {blob.length} bytes)")

    if not blob_name.endswith(ZIP_SUFFIX):
        logging.warning(f"Skipping blob with unexpected name: {blob_name}")
        return

    build_id = blob_name[:-len(ZIP_SUFFIX)]
    logging.info(f"Extracted build_id: {build_id}")

    tmp_zip_path = None  # Initialize tmp_zip_path
    try:
        # Write blob content to a temporary zip file
        with tempfile.NamedTemporaryFile(delete=False, suffix=ZIP_SUFFIX) as tmp_zip:
            tmp_zip.write(blob.read())
            tmp_zip_path = tmp_zip.name

        logging.info(f"Temporary ZIP saved to: {tmp_zip_path}")

        # Process the run data from the ZIP
        process_run_data(tmp_zip_path, build_id)
        logging.info(f"Successfully processed run data for build_id: {build_id}")

    except Exception as e:
        logging.error(f"Error processing run data for build_id {build_id}: {e}")

    finally:
        # Clean up temporary ZIP file
        if tmp_zip_path and os.path.exists(tmp_zip_path): # Safely check and delete
            os.remove(tmp_zip_path)
            logging.info(f"Deleted temporary ZIP: {tmp_zip_path}")
