import requests
import datetime

requests.post("http://127.0.0.1:5001/add", json={"h119": "stupid", "added_by": "shlawg", "tag": "blatant", "notes": "hi xander"})


response = requests.get("http://localhost:5001/query-all")
for i in response.json():
    print(datetime.datetime.strptime(i[4], "%Y-%m-%d %H:%M:%S"))
print(response.json())