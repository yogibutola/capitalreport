from app.store.mongo.pb_league_store import PBLeagueStore
from app.store.mongo.pb_mongo_db_store import PBMongoDBStore

def test_get_all_leagues():
    print("Testing PBLeagueStore.get_all_leagues()...")
    league_store = PBLeagueStore()
    leagues = league_store.get_all_leagues()
    print(f"Leagues (PBLeagueStore): {leagues}")
    if isinstance(leagues, list) and (len(leagues) == 0 or (isinstance(leagues[0], dict) and "league_name" in leagues[0] and "league_status" in leagues[0])):
        print("✅ PBLeagueStore test passed!")
    else:
        print("❌ PBLeagueStore test failed!")

    print("\nTesting PBMongoDBStore.get_all_leagues()...")
    mongo_store = PBMongoDBStore()
    leagues_mongo = mongo_store.get_all_leagues()
    print(f"Leagues (PBMongoDBStore): {leagues_mongo}")
    if isinstance(leagues_mongo, list) and (len(leagues_mongo) == 0 or (isinstance(leagues_mongo[0], dict) and "league_name" in leagues_mongo[0] and "league_status" in leagues_mongo[0])):
        print("✅ PBMongoDBStore test passed!")
    else:
        print("❌ PBMongoDBStore test failed!")

if __name__ == "__main__":
    test_get_all_leagues()
