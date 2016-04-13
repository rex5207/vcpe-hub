"""Database update."""
from pymongo import MongoClient


def update_data_to_db(item, data, db_ip, db):
    client = MongoClient(db_ip, 27017)
    database = client[db]

    # application
    if item == 1:
        collection = database["App_collection"]
        for key in data:
            db_data = collection.find({'appname': key}).limit(1)

            if db_data.count() != 0:
                # Update
                collection.update({'appname': key},
                                  {'$set': {'rate': data.get(key).rate, 'key': 1}})
            else:
                collection.insert({'appname': key, 'rate': data.get(key).rate,
                                  'key': 1})

        collection.remove({"key": 0})
        collection.update({'key': 1}, {'$set': {'key': 0}},\
                          upsert=False, multi=True)

    # member
    elif item == 2:
        collection = database["App_collection_for_memeber"]
        for key in data:
            db_data = collection.find({'membername': key}).limit(1)
            content = []
            for app in data.get(key).apprate:
                if app is None:
                    content.append({'None': data.get(key).apprate.get(app)})
                else:
                    appname = str(app).replace(".", ",")
                    content.append({appname: data.get(key).apprate.get(app)})

            if db_data.count() != 0:
                    # Update
                    collection.update({'membername': key},
                                      {'$set': {'app': content, 'key': 1}})
            else:
                collection.insert({'membername': key, 'app': content, 'key': 1})

        collection.remove({"key": 0})
        collection.update({'key': 1}, {'$set': {'key': 0}},\
                          upsert=False, multi=True)
