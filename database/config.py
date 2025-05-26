import logging
import psycopg2
from azure.identity import ManagedIdentityCredential
from contextlib import contextmanager

from database.constants import COMMON_CONFIG, DB_HOSTS, CONN_MI, TOKEN_URL

class DatabaseConnector:
    """
    A class for managing connections to PostgreSQL databases using Azure Managed Identity.
    The class handles connection creation, caching, and proper cleanup.
    """
    _instances = {}  # Dictionary to store connections by IHV

    def __init__(self):
        """Initialize the DatabaseConnector with empty connections dictionary."""
        self._connections = {}
        
    def __del__(self):
        """Ensure all connections are closed when the object is destroyed."""
        self.close_all_connections()
        
    def get_connection(self, ihv):
        """
        Get a database connection for the specified IHV.
        Creates a new connection if one doesn't exist or reuses an existing connection.
        
        Args:
            ihv (str): The IHV identifier ('Cadmus', 'LNL', or 'STRX')
            
        Returns:
            connection: A PostgreSQL database connection or None if connection fails
        """
        if ihv not in DB_HOSTS:
            logging.error(f"Unknown IHV: {ihv}")
            return None
            
        # Return existing connection if it exists and is open
        if ihv in self._connections:
            try:
                # Check if connection is still valid
                with self._connections[ihv].cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return self._connections[ihv]  # Connection is valid
            except (psycopg2.OperationalError, psycopg2.InterfaceError):
                # Connection is closed or broken, will recreate
                logging.info(f"Connection for {ihv} is no longer valid, recreating...")
                self._connections[ihv] = None
        
        # Create a new connection
        try:
            # Get Azure Managed Identity access token
            credential = ManagedIdentityCredential(client_id=COMMON_CONFIG["managed_identity_name"])
            token = credential.get_token(TOKEN_URL)
            
            # Build connection parameters
            conn_params = {
                "host": DB_HOSTS[ihv],
                "port": COMMON_CONFIG["port"],
                "database": COMMON_CONFIG["database"],
                "user": CONN_MI,
                "password": token.token,
                "sslmode": "require"
            }
            
            # Create and store the connection
            self._connections[ihv] = psycopg2.connect(**conn_params)
            logging.info(f"Successfully connected to {ihv} database")
            return self._connections[ihv]
            
        except Exception as e:
            logging.error(f"Failed to connect to {ihv} database: {str(e)}")
            return None
    
    def close_connection(self, ihv):
        """
        Close a specific IHV connection.
        
        Args:
            ihv (str): The IHV identifier to close connection for
        """
        if ihv in self._connections and self._connections[ihv]:
            try:
                self._connections[ihv].close()
                logging.info(f"Closed connection to {ihv} database")
            except Exception as e:
                logging.error(f"Error closing connection to {ihv} database: {str(e)}")
            finally:
                self._connections[ihv] = None
    
    def close_all_connections(self):
        """Close all open database connections."""
        for ihv in list(self._connections.keys()):
            self.close_connection(ihv)
    
    @classmethod
    def get_instance(cls):
        """
        Get a singleton instance of DatabaseConnector.
        
        Returns:
            DatabaseConnector: A singleton instance of the DatabaseConnector
        """
        # Using the current thread ID as a key for the singleton
        import threading
        thread_id = threading.get_ident()
        
        if thread_id not in cls._instances:
            cls._instances[thread_id] = DatabaseConnector()
        return cls._instances[thread_id]

# Context manager for database connections
@contextmanager
def db_connection(ihv):
    """
    Context manager for database connections.
    
    Args:
        ihv (str): The IHV identifier
        
    Yields:
        connection: A PostgreSQL database connection
    """
    connector = DatabaseConnector.get_instance()
    conn = connector.get_connection(ihv)
    try:
        yield conn
    finally:
        # We don't close the connection here to allow connection pooling
        # Connections will be closed when the DatabaseConnector is destroyed
        pass