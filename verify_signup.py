from app.store.pb_mongo_db_store import PBMongoDBStore

store = PBMongoDBStore()
collection = store.get_players_collection()
players = list(collection.find())
print(f"Total players in DB: {len(players)}")
for p in players:
    print(f"Player: {p.get('firstName')} {p.get('lastName')} ({p.get('email')})")
