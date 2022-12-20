import boto3
import json

dynamodb = boto3.client('dynamodb')

def upload():
    with open('data.json', 'r') as datafile:
        records = json.load(datafile)
    for song in records:
        print(song)
        item = {
                'artist':{'S':song['artist']},
                'song':{'S':song['song']},
                'id':{'S': song['id']},
                'priceUsdCents':{'S': str(song['priceUsdCents'])},
                'publisher':{'S': song['publisher']}
        }
        print(item)
        response = dynamodb.put_item(
            TableName='basicSongsTable', 
            Item=item
        )
        print("UPLOADING ITEM")
        print(response)

upload()