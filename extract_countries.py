import json
import os
import pymongo
import argparse
from bson import json_util
from dotenv import load_dotenv
load_dotenv()

parser = argparse.ArgumentParser()

parser.add_argument('-o', type=str, default='output.json',
                    help='Output file name')
parser.add_argument('--country', type=str, default='',
                    help='Country to export (default: it will export all countries)')

args = parser.parse_args()

mongodb = pymongo.MongoClient(
    f"mongodb+srv://{os.getenv('MONGODB_USER')}:{os.getenv('MONGODB_PASSWORD')}@mining.uqmew.mongodb.net")

query = {}
if args.country != '':
    query['tags'] = {
        '$in': [args.country.lower().strip()]
    }
result = mongodb['mining']['adminsplaces_news'].find(query)
open(args.o, 'w').write(json_util.dumps(result))

print(f"Found {result.retrieved} places")
