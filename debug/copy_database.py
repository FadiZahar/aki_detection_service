import sqlite3

def copy_database(source_db_path: str, destination_db_path: str):
    # Connect to the source and destination databases
    source_conn = sqlite3.connect(source_db_path)
    dest_conn = sqlite3.connect(destination_db_path)
    
    # Get the list of all tables from the source database
    source_cursor = source_conn.cursor()
    source_cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = source_cursor.fetchall()

    # For each table in the source database, copy its schema and data to the destination database
    for table_name in tables:
        table_name = table_name[0]
        print(f"Copying table: {table_name}")
        
        # Get the CREATE TABLE statement for the current table
        source_cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}';")
        create_table_sql = source_cursor.fetchone()[0]
        
        # Create the table in the destination database
        dest_cursor = dest_conn.cursor()
        dest_cursor.execute(create_table_sql)
        
        # Copy all rows from the source table to the destination table
        source_cursor.execute(f"SELECT * FROM {table_name};")
        rows = source_cursor.fetchall()
        for row in rows:
            placeholders = ', '.join(['?'] * len(row))
            dest_cursor.execute(f"INSERT INTO {table_name} VALUES ({placeholders});", row)
        
        # Commit the changes to the destination database
        dest_conn.commit()
    
    print("Database copy completed successfully.")
    
    # Close all connections
    source_conn.close()
    dest_conn.close()

# Example usage
source_db_path = 'database_replace/my_copied_database.db'
destination_db_path = '/state/my_database.db'
copy_database(source_db_path, destination_db_path)
