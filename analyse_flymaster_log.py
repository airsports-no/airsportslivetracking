import datetime
from io import StringIO
import json
import pandas as pd
import dateutil
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Read the JSON file
# with open("downloaded-logs-20240819-093409.json", "r") as f:
with open("downloaded-logs-20240822-102546.json", "r") as f:
    data = json.load(f)

# Extract 'textPayload' values
text_payloads = [entry["textPayload"] for entry in data if "textPayload" in entry]
time_stamps = [dateutil.parser.parse(entry["timestamp"]) for entry in data]
data = []
all_reports = []
for index, text in enumerate(text_payloads):
    start = text.find("'data': ['") + len("'data': ['")
    end = text.find("]", start)
    csv_data = text[start : end - 1]  # .split("\\n")
    csv_data = csv_data.replace("\\n", "\n")
    data.append(csv_data)
    # # Read the CSV data into a DataFrame
    # df = pd.read_csv(StringIO(csv_data), header=None, lineterminator="\n", names=range(9))
    # df = df.dropna(subset=[2])
    # df[0] = df[0].apply(lambda x: datetime.datetime.fromtimestamp(float(x)).replace(tzinfo=datetime.timezone.utc))
    # df[1] = df[1].apply(lambda x: datetime.datetime.fromtimestamp(float(x)).replace(tzinfo=datetime.timezone.utc))
    # df["received_time"] = time_stamps[index]
    # all_reports.append(df)

with open("parsed_flymaster_posts_task1and2.json", "w") as o:
    json.dump(data, o)

# final = pd.concat(all_reports)
# final.reset_index(drop=True, inplace=True)
# print(final.head(50))
# plt.figure()
# plt.plot((final["received_time"] - final[1]).dt.total_seconds())
# plt.savefig("temporary_plot.png")
