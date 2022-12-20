import boto3

dynamodb = boto3.client("dynamodb")

response = dynamodb.create_table(
  TableName="basicSongsTable",
  AttributeDefinitions=[
    {
      "AttributeName": "artist",
      "AttributeType": "S"
    },
    {
      "AttributeName": "song",
      "AttributeType": "S"
    }
  ],
  KeySchema=[
    {
      "AttributeName": "artist",
      "KeyType": "HASH"
    },
    {
      "AttributeName": "song",
      "KeyType": "RANGE"
    }
  ],
  ProvisionedThroughput={
    "ReadCapacityUnits": 1,
    "WriteCapacityUnits": 1
  }
)

print(response)