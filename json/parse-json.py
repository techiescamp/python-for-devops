import json
import os

# Script to create absolute path of the JSON file.

script_dir = os.path.dirname(__file__)
print("The Script is located at:" + script_dir )
script_absolute_path = os.path.join(script_dir, 'files/example.json')
print("The Script Path is:" + script_absolute_path)

# Script to parse JSON

json = json.loads(open(script_absolute_path).read())
value = json['name']
print(value)

# Loop through JSON

for key in json:
    value = json[key]
    print("The key and value are ({}) = ({})".format(key, value))