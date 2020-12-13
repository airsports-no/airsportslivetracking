import requests

# data = requests.post("https://tracking.airsports.no/api/v1/contests/",
#                      headers={
#                          'Authorization': 'Token cca2a734cfc40b54e4192475befdce083b2ff90f',
#                          'Content-Type': 'application/json'
#                      },
#                      json={"name": "My test contest"}
#                      )
# print(data)
# print(data.json())
# i = data.json()['id']
# print(i)
i = 20
data = requests.delete("https://tracking.airsports.no/api/v1/contests/{}/".format(i),
                       headers={
                           'Authorization': 'Token cca2a734cfc40b54e4192475befdce083b2ff90f',
                           'Content-Type': 'application/json'
                       },
                       )
print(data)
print(data.text)