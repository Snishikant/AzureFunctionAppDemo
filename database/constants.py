# Common configuration across all databases
CONN_MI = "wssi-db-connection-mi"
WORKLOADS_TABLE_NAME = "grfxml_workloads"
TOKEN_URL = "https://ossrdbms-aad.database.windows.net/.default"

COMMON_CONFIG = {
    "port": "5432",
    "database": "wssigfx",
    "managed_identity_name": "wssi-db-connection-mi"
}

DB_HOSTS = {
    "Cadmus": "wssigfx-qb.postgres.database.azure.com",
    "LNL": "wssigfx-i.postgres.database.azure.com",
    "STRX": "wssigfx-a.postgres.database.azure.com"
}

ihv_dict = {
        'x64_vitis': 'STRX',
        'x64_ov': 'LNL',
        'arm64_npu': 'Cadmus'
}