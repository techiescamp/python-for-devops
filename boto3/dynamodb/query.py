import boto3
import json
from boto3.dynamodb.conditions import Key

TABLE_NAME = "basicSongsTable"

# Creating the DynamoDB Client
dynamodb_client = boto3.client('dynamodb', region_name="us-west-2")

# Creating the DynamoDB Table Resource
dynamodb = boto3.resource('dynamodb', region_name="us-west-2")
table = dynamodb.Table(TABLE_NAME)


artists = table.scan(AttributesToGet=['artist.'])


specific_artist = table.query(
  KeyConditionExpression=Key('artist').eq('Arturus Ardvarkian')
)

artists_object = json.dumps(artists, indent = 4) 
print(artists_object)

specific_artist = json.dumps(specific_artist, indent = 4) 
print(specific_artist)