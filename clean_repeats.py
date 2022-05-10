import pymongo
import os
from dotenv import load_dotenv
load_dotenv()

mongodb = pymongo.MongoClient(
    f"mongodb+srv://{os.getenv('MONGODB_USER')}:{os.getenv('MONGODB_PASSWORD')}@mining.uqmew.mongodb.net")


def delete_repeated_attractions(place):
    """
    Deletes the repeated attractions from the place.
    """
    repeated_attractions = list(mongodb['mining']['adminsplaces_news'].find({
        'googlePlaceId': place['_id']}))
    max_locations = 0
    max_id = None
    for repeated_attraction in repeated_attractions:
        if len(repeated_attraction['location']) > max_locations:
            max_locations = len(repeated_attraction['location'])
            max_id = repeated_attraction['_id']

    if max_id is not None:
        for repeated_attraction in repeated_attractions:
            if repeated_attraction['_id'] == max_id:
                continue
            mongodb['mining']['adminsplaces_news'].delete_one(
                {'_id': repeated_attraction['_id']})


result = list(mongodb['mining']['adminsplaces_news'].aggregate([
    {
        '$group': {
            '_id': '$googlePlaceId',
            'count': {
                '$sum': 1
            }
        }
    }, {
        '$match': {
            'count': {
                '$gt': 1
            }
        }
    }
]))

for i in range(len(result)):
    print(f"{i}/{len(result)}")
    delete_repeated_attractions(result[i])
