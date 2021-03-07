cd C:\Users\frank\Documents\live_tracking_map\MSFS2020_client\
C:\Users\frank\AppData\Local\Programs\Python\Python37\python -m build
cd \airsports
pyoxidizer run


pyinstaller -F --onefile --add-data "client/airsports.png;." --add-data "client/SimConnectCust;client/SimConnectCust" --noconsole client/airsports_client.py