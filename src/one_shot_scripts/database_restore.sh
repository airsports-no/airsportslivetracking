#!/bin/bash

# Before starting, update your docker-compose.yml or Docker startup flags to disable disk-syncing overhead. This can speed up the import by 3x–5x. Remembered to restore these settings after the import to avoid data loss in production!
# services:
#   mysql:
#     image: mysql:8.0
#     container_name: mysql
#     command: 
#       - --innodb_flush_log_at_trx_commit=2
#       - --innodb_doublewrite=0
#       - --sync_binlog=0
#       - --innodb_redo_log_capacity=4G
#       - --max_allowed_packet=1G
#       - --innodb_buffer_pool_size=8G  # Set to ~50% of your available RAM

# --- Configuration ---
CONTAINER_NAME="mysql"
DB_USER="root"
LOCAL_SQL_PATH=$1
TEMP_CONTAINER_PATH="/tmp/restore_backup.sql"

# Check if file argument exists
if [ -z "$1" ]; then
    echo "❌ Usage: ./master_import.sh <path_to_huge_sql_file>"
    exit 1
fi


echo "🕒 Step 1/4: Copying 58GB file into container (this will take a while)..."
docker cp "$LOCAL_SQL_PATH" "$CONTAINER_NAME":"$TEMP_CONTAINER_PATH"



# echo "🧹 Step 2/4: Stripping Cloud SQL DEFINERS inside the container..."
# Doing this inside the container saves host CPU/RAM
# docker exec -it "$CONTAINER_NAME" sed -i 's/DEFINER=[^*]*\*/\*/g' "$TEMP_CONTAINER_PATH"

echo "⚡ Step 3/4: Disabling foreign key checks for the session..."
# We wrap the import in a command block to ensure checks are off during the massive insert
IMPORT_CMD="SET GLOBAL foreign_key_checks = 0; SET GLOBAL unique_checks = 0; SOURCE $TEMP_CONTAINER_PATH; SET GLOBAL foreign_key_checks = 1; SET GLOBAL unique_checks = 1;"

echo "📥 Step 4/4: Starting high-speed internal restore..."
echo "Note: You will be prompted for the MySQL root password."

docker exec -it "$CONTAINER_NAME" mysql -u "$DB_USER" -p --max_allowed_packet=1G -e "$IMPORT_CMD"

if [ $? -eq 0 ]; then
    echo "✅ Success! 58GB Import Complete."
    echo "🗑️ Cleaning up temp file in container..."
    docker exec -it "$CONTAINER_NAME" rm "$TEMP_CONTAINER_PATH"
else
    echo "❌ Error: Import failed. Check Docker logs or disk space."
fi