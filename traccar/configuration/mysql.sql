CREATE DATABASE IF NOT EXISTS traccar;
CREATE USER 'traccar'@'localhost' IDENTIFIED BY 'traccar';
CREATE USER 'traccar'@'%' IDENTIFIED BY 'traccar';
GRANT ALL PRIVILEGES ON traccar.* To 'traccar'@'localhost';
GRANT ALL PRIVILEGES ON traccar.* To 'traccar'@'%';
FLUSH PRIVILEGES;