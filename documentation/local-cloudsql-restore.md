# Restore Cloud SQL export into local docker-compose MySQL

This document explains how to load a Cloud SQL export containing the `tracker` and `traccar` databases into the local Docker Compose MySQL container used by this project.

Warning: this procedure deletes the current local contents of the `tracker` and `traccar` databases before importing the dump.

It is based on the current local setup in:
- `docker-compose.yml`
- `traccar_local_config/configuration/mysql.sql`
- `traccar_local_config/configuration/traccar.xml`

Current local defaults in this repo:
- MySQL container/service: `mysql`
- Root password: `traccar`
- Django database: `tracker` using user `tracker` / password `tracker`
- Traccar database: `traccar` using user `traccar` / password `traccar`

## Expected dump formats

This guide supports either of these common cases:

1. Two SQL files:
   - `tracker.sql`
   - `traccar.sql`

2. One combined SQL file that already contains `CREATE DATABASE` / `USE` statements for both databases.

If your download is compressed (`.gz` or `.tar.gz`), extract it first or stream it with `gunzip -c`.

## 1. Stop services that may write to the databases

From the repo root:

```bash
docker compose stop tracker_daphne tracker_celery tracker_processor live_calculator traccar
```

Leave `mysql` running, or start it if needed:

```bash
docker compose up -d mysql
```

Optional: confirm MySQL is reachable:

```bash
docker exec mysql mysql -uroot -ptraccar -e "SHOW DATABASES;"
```

## 2. Drop and recreate the application databases

This wipes the old local data while keeping the container, users, and volume in place.

```bash
docker exec mysql mysql -uroot -ptraccar -e "DROP DATABASE IF EXISTS tracker; CREATE DATABASE tracker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; DROP DATABASE IF EXISTS traccar; CREATE DATABASE traccar CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE USER IF NOT EXISTS 'tracker'@'%' IDENTIFIED BY 'tracker'; CREATE USER IF NOT EXISTS 'traccar'@'%' IDENTIFIED BY 'traccar'; GRANT ALL PRIVILEGES ON tracker.* TO 'tracker'@'%'; GRANT ALL PRIVILEGES ON traccar.* TO 'traccar'@'%'; FLUSH PRIVILEGES; SET GLOBAL net_buffer_length=1000000; SET GLOBAL max_allowed_packet=2147483648;"
```

Notes:
- The root password in local compose is `traccar`.
- The repo's MySQL container already starts with an elevated `--max_allowed_packet`, but the command above also sets a large runtime value before import.

## 3A. Import when you have separate `tracker.sql` and `traccar.sql` files

Example if the files are in `~/Downloads/cloudsql-export/`:

```bash
docker exec -i mysql sh -c 'mysql -uroot -ptraccar --max_allowed_packet=2000M tracker' < ~/Downloads/cloudsql-export/tracker.sql

docker exec -i mysql sh -c 'mysql -uroot -ptraccar --max_allowed_packet=2000M traccar' < ~/Downloads/cloudsql-export/traccar.sql
```

If the files are gzipped:

```bash
gunzip -c ~/Downloads/cloudsql-export/tracker.sql.gz | docker exec -i mysql sh -c 'mysql -uroot -ptraccar --max_allowed_packet=2000M tracker'

gunzip -c ~/Downloads/cloudsql-export/traccar.sql.gz | docker exec -i mysql sh -c 'mysql -uroot -ptraccar --max_allowed_packet=2000M traccar'
```

## 3B. Import when you have one combined SQL dump

Use this only if the SQL file already contains `CREATE DATABASE`, `USE tracker`, and `USE traccar` statements.

```bash
docker exec -i mysql sh -c 'mysql -uroot -ptraccar --max_allowed_packet=2000M' < ~/Downloads/cloudsql-export/all-databases.sql
```

If gzipped:

```bash
gunzip -c ~/Downloads/cloudsql-export/all-databases.sql.gz | docker exec -i mysql sh -c 'mysql -uroot -ptraccar --max_allowed_packet=2000M'
```

If the combined file does not contain database-selection statements, split it into separate `tracker.sql` and `traccar.sql` files and use section 3A instead.

## 4. Verify that the import landed

Check that both databases exist and contain tables:

```bash
docker exec mysql mysql -uroot -ptraccar -e "SELECT table_schema, COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema IN ('tracker','traccar') GROUP BY table_schema ORDER BY table_schema;"
```

Optional spot checks:

```bash
docker exec mysql mysql -uroot -ptraccar -e "USE tracker; SHOW TABLES;"
docker exec mysql mysql -uroot -ptraccar -e "USE traccar; SHOW TABLES;"
```

## 5. Start the local stack again

Once the import completes:

```bash
docker compose up -d traccar tracker_daphne tracker_celery tracker_processor live_calculator
```

`tracker_daphne` starts with:
- `python3 manage.py migrate`
- `python3 manage.py initadmin`
- `python3 manage.py createdefaultscores`

So if your dump is slightly behind the current code's schema, the local Django app will apply pending migrations on startup.

## Recommended full example

If your export unpacks into `tracker.sql` and `traccar.sql` under `~/Downloads/db_restore/`:

```bash
docker compose stop tracker_daphne tracker_celery tracker_processor live_calculator traccar
docker compose up -d mysql

docker exec mysql mysql -uroot -ptraccar -e "DROP DATABASE IF EXISTS tracker; CREATE DATABASE tracker CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; DROP DATABASE IF EXISTS traccar; CREATE DATABASE traccar CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci; CREATE USER IF NOT EXISTS 'tracker'@'%' IDENTIFIED BY 'tracker'; CREATE USER IF NOT EXISTS 'traccar'@'%' IDENTIFIED BY 'traccar'; GRANT ALL PRIVILEGES ON tracker.* TO 'tracker'@'%'; GRANT ALL PRIVILEGES ON traccar.* TO 'traccar'@'%'; FLUSH PRIVILEGES; SET GLOBAL net_buffer_length=1000000; SET GLOBAL max_allowed_packet=2147483648;"

docker exec -i mysql sh -c 'mysql -uroot -ptraccar --max_allowed_packet=2000M tracker' < ~/Downloads/db_restore/tracker.sql
docker exec -i mysql sh -c 'mysql -uroot -ptraccar --max_allowed_packet=2000M traccar' < ~/Downloads/db_restore/traccar.sql

docker exec mysql mysql -uroot -ptraccar -e "SELECT table_schema, COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema IN ('tracker','traccar') GROUP BY table_schema ORDER BY table_schema;"

docker compose up -d traccar tracker_daphne tracker_celery tracker_processor live_calculator
```

## If you want a completely fresh MySQL volume instead

Usually you do not need this; dropping and recreating the two databases is enough.

If the local MySQL volume is badly corrupted and you want to destroy everything in it, stop the stack and remove the compose volume:

```bash
docker compose down

docker volume rm airsportslivetracking_mysqldata3

docker compose up -d mysql
```

After that, re-run the import steps above.

Use caution: removing the volume deletes all local MySQL databases in that container, not just `tracker` and `traccar`.
