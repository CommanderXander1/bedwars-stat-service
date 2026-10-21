import requests

# requests.post("http://127.0.0.1:5000/add", json={"username": "tardied", "added_by": "shlawg", "tag": "blatant", "notes": "hi xander"})


response = requests.get("http://localhost:5000/query-all")
print(response.json())