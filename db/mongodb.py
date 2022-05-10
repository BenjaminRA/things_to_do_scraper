import os
import pymongo
from dotenv import load_dotenv
load_dotenv()


def get_client():
    mongodb = pymongo.MongoClient(
        f"mongodb+srv://{os.getenv('MONGODB_USER')}:{os.getenv('MONGODB_PASSWORD')}@{os.getenv('MONGODB_HOST')}")

    print(
        f"mongodb+srv://<username>:<password>@{os.getenv('MONGODB_HOST')}")

    return mongodb['mining']
