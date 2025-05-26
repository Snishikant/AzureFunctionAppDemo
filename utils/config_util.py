from pathlib import Path

# testcase specific variable
platforms = ['x64_vitis', 'x64_ov', 'arm64_npu']
models = ['qp', 'embeddings_d3', 'embeddings_d5', 'embeddings_d3_c', 'semtext', 'srd', 'llm', 'ner', 'tcm', 'imdesc']
tests = ['Prediction', 'Evaluation']

# log specific variable
DATA_DIR = Path("pipeline_data")
LOGS_DIR = DATA_DIR / "logs"
ARTIFACTS_DIR = DATA_DIR / "artifacts"
ZIP_SUFFIX = "_run_data.zip"