import os
from pymongo import MongoClient
from dotenv import load_dotenv
load_dotenv()

print(os.getenv('MONGO_URI'))
cluster = MongoClient(os.getenv('MONGO_URI'))
db = cluster.get_database("PaceBot")
serversCol = db.get_collection("Servers")

async def get_server_data():
    return await serversCol.find({})

async def update_server(server_id, update_data):
    return await serversCol.update_one({"serverId": server_id}, {"$set": update_data}, upsert=True)
