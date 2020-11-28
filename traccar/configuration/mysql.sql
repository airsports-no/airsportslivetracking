CREATE DATABASE IF NOT EXISTS traccar;
CREATE DATABASE IF NOT EXISTS tracker;

CREATE USER 'traccar'@'%' IDENTIFIED BY 'traccar';
CREATE USER 'tracker'@'%' IDENTIFIED BY 'tracker';

GRANT ALL PRIVILEGES ON traccar.* To 'traccar'@'%';
GRANT ALL PRIVILEGES ON tracker.* To 'tracker'@'%';
FLUSH PRIVILEGES;
