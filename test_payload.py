import json
from app.vo.pb.slotting_details_payload import SlottingDetailsPayload

payload_dict = {
  "league_id": "123",
  "league_name": "Test",
  "rounds": [
    {
      "round_id": 1,
      "group": [
        {
          "group_id": 1,
          "group_name": "Group 1",
          "group_size": 4,
          "match": [
            {
              "match_id": "m1",
              "league_id": "123",
              "league_name": "Test",
              "round_id": 1,
              "group_id": 1,
              "time": "2024-02-24T09:00:00",
              "court_number": "1",
              "team_one": {
                "team_id": "t1",
                "team_name": "Team 1",
                "score": 0,
                "player_one": {
                  "firstName": "A",
                  "lastName": "B",
                  "email": "a@b.com"
                },
                "player_two": {
                  "firstName": "C",
                  "lastName": "D",
                  "email": "c@d.com"
                }
              },
              "team_two": {
                "team_id": "t2",
                "team_name": "Team 2",
                "score": 0,
                "player_one": {
                  "firstName": "E",
                  "lastName": "F",
                  "email": ""
                },
                "player_two": {
                  "firstName": "G",
                  "lastName": "H",
                  "email": "g@h.com"
                }
              }
            }
          ]
        }
      ]
    }
  ]
}

try:
    obj = SlottingDetailsPayload(**payload_dict)
    print("Success!")
except Exception as e:
    print(e)
