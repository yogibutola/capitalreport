from bson import ObjectId
from app.store.mongo.pb_league_store import PBLeagueStore
from app.store.mongo.pb_player_store import PBPlayerStore
from app.vo.pb.league import League
from app.vo.pb.match import Match
from app.vo.pb.match_details_payload import MatchDetailsPayload
from app.vo.pb.slotting_details_payload import SlottingDetailsPayload
from app.store.mongo.pb_match_store import PBMatchStore



class PBLeagueService:
    def __init__(self, pb_league_store: PBLeagueStore):
        self.pb_league_store = pb_league_store
        self.pb_match_store = PBMatchStore()

    def get_league_details(self):
        return "League details"

    def get_match_details(self):
        return "Match details"

    def get_team_details(self):
        return "Team details"

    def get_team_stats(self):
        return "Team stats"

    def get_match_stats(self):
        return "Match stats"

    def get_player_match_stats(self):
        return "Player match stats"

    def get_team_match_stats(self):
        return "Team match stats"

    def save_league_details(self, league_details: League):
        self.pb_league_store.store_new_league_details(league_details)

    def get_all_leagues(self) -> list[dict]:
        return self.pb_league_store.get_all_leagues()

    def get_league_by_status(self, league_status: str):
        return self.pb_league_store.get_league_by_status(league_status)

    def get_players_by_league_id(self, league_id: str):
        return self.pb_league_store.get_players_by_league_id(league_id)

    def update_league_with_round_details(self, slotting_details: SlottingDetailsPayload):
        # Extract match details from the slotting details
        matches = []
        for round_item in slotting_details.rounds:
            for group_item in round_item.group:
                group_item.group_size = len(group_item.match)
                for match_item in group_item.match:
                    matches.append(match_item)
                # Remove match details from group after extraction
                group_item.match = []
        
        # Save league details (now without match information)
        self.pb_league_store.update_league_with_round_details(slotting_details)
        
        # Save extracted match details separately
        self.pb_match_store.store_match_details(matches)

    def get_league_details_by_league_name(self, league_name: str):
        league_details = self.pb_league_store.get_league_details_by_league_name(league_name)
        if league_details and "_id" in league_details:
            matches = self.pb_match_store.get_match_details_by_league_id(league_details["_id"])
            # Convert matches to serializable format
            for match in matches:
                if "_id" in match:
                    # We can either remove _id or convert it to a string. 
                    # Match model uses match_id, so we can just remove _id.
                    del match["_id"]
            
            league_details["league_id"] = str(league_details["_id"])
            del league_details["_id"]
            league_details["matches"] = matches
        return league_details

    def save_match_score(self, match_details: MatchDetailsPayload):
        self.pb_match_store.save_match_score(match_details)
        
        # Trigger group completion check
        if match_details.match_status == "completed":
            match = self.pb_match_store.get_match(match_details.league_id, match_details.match_id)
            if match:
                 # Ensure round_id is int if coming from legacy DB data
                try: 
                    r_id = int(match.get("round_id"))
                    g_id = int(match.get("group_id"))
                except (ValueError, TypeError):
                    return # Or handle error
                self.check_group_completion(match_details.league_id, r_id, g_id)

    def register_player(self, league_id: str, email: str):
        # 1. Fetch player details
        pb_player_store = PBPlayerStore()
        player_doc = pb_player_store.find_player_by_email(email)
        if not player_doc:
            raise ValueError(f"Player with email {email} not found")

        # 2. Fetch league details
        league_collection = self.pb_league_store.get_league_collection()
        league_doc = league_collection.find_one({"_id": ObjectId(league_id)})
        if not league_doc:
            raise ValueError(f"League with ID {league_id} not found")

        # 3. Add player to league collection
        player_data = {
            "firstName": player_doc["firstName"],
            "lastName": player_doc["lastName"],
            "email": player_doc["email"],
            "dupr_rating": player_doc.get("dupr_rating")
        }
        self.pb_league_store.add_player_to_league(league_id, player_data)

        # 4. Update player record with league info
        league_info = {
            "league_id": str(league_doc["_id"]),
            "league_name": league_doc["league_name"],
            "league_type": league_doc.get("league_type", "PB"),
            "league_status": league_doc.get("league_status") or league_doc.get("status"),
            "league_start_date": league_doc.get("league_start_date"),
            "league_end_date": league_doc.get("league_end_date")
        }
        pb_player_store.bulk_update_players_league_details([email], league_info)

    def withdraw_player(self, league_id: str, email: str, play_day: int, reason: str):
        # 1. Fetch player details
        pb_player_store = PBPlayerStore()
        player_doc = pb_player_store.find_player_by_email(email)
        if not player_doc:
            raise ValueError(f"Player with email {email} not found")

        # 2. Fetch league details
        league_doc = self.pb_league_store.get_league_details(league_id)
        if not league_doc:
            raise ValueError(f"League with ID {league_id} not found")
        
        # 3. Add withdrawal to league
        withdrawal_data = {
            "email": email,
            "play_day": play_day,
            "reason": reason
        }
        self.pb_league_store.add_withdrawal(league_id, withdrawal_data)

    def check_group_completion(self, league_id: str, round_id: int, group_id: int):
        matches = self.pb_match_store.get_matches_by_group(league_id, round_id, group_id)
        if not matches:
            return

        league_doc = self.pb_league_store.get_league_details(league_id)
        if not league_doc:
            return

        rounds = league_doc.get("rounds", [])
        target_round = next((r for r in rounds if int(r.get("round_id", -1)) == round_id), None)
        if not target_round:
            return

        target_group = next((g for g in target_round.get("group", []) if int(g.get("group_id", -1)) == group_id), None)
        if not target_group:
            return

        target_group_size = target_group.get("group_size")
        if target_group_size is not None and len(matches) != target_group_size:
            return

        # Check if all matches are completed
        all_complete = all(m.get("match_status") == "completed" for m in matches)
        if all_complete and len(matches) > 0:
            self.process_group_promotion_relegation(league_id, round_id, group_id, matches)

    def calculate_group_standings(self, matches: list) -> list[dict]:
        player_stats = {}

        for match in matches:
            t1 = match.get("team_one", {})
            t2 = match.get("team_two", {})
            s1 = t1.get("score", 0)
            s2 = t2.get("score", 0)

            p1 = t1.get("player_one", {})
            p2 = t1.get("player_two", {})
            p3 = t2.get("player_one", {})
            p4 = t2.get("player_two", {})

            # Helper to init stats
            for p in [p1, p2, p3, p4]:
                if not p or not p.get("email"):
                    continue
                email = p["email"]
                if email not in player_stats:
                    player_stats[email] = {
                        "player": p,
                        "wins": 0,
                        "losses": 0,
                        "point_diff": 0,
                        "points_won": 0
                    }

            # Update stats
            # Assuming team_one wins if s1 > s2
            # Also checking for sitting players if any (though match VO suggests 2v2 usually)
            
            # Team 1 Players
            for p_dict in [p1, p2]:
                if not p_dict or not p_dict.get("email"): continue
                stats = player_stats[p_dict["email"]]
                stats["points_won"] += s1
                stats["point_diff"] += (s1 - s2)
                if s1 > s2:
                    stats["wins"] += 1
                elif s2 > s1:
                    stats["losses"] += 1

            # Team 2 Players
            for p_dict in [p3, p4]:
                if not p_dict or not p_dict.get("email"): continue
                stats = player_stats[p_dict["email"]]
                stats["points_won"] += s2
                stats["point_diff"] += (s2 - s1)
                if s2 > s1:
                    stats["wins"] += 1
                elif s1 > s2:
                    stats["losses"] += 1

        # Sort: Wins DESC, Point Diff DESC, Points Won DESC
        sorted_players = sorted(
            player_stats.values(),
            key=lambda x: (x["wins"], x["point_diff"], x["points_won"]),
            reverse=True
        )
        return sorted_players

    def process_group_promotion_relegation(self, league_id: str, round_id: int, group_id: int, matches: list):
        standings = self.calculate_group_standings(matches)
        if not standings:
            return

        league_doc = self.pb_league_store.get_league_details(league_id)
        if not league_doc:
            return

        # Determine next round ID
        current_round_num = round_id
        next_round_num = current_round_num + 1
        next_round_id = next_round_num
            
        current_group_num = group_id

        # Logic:
        # Top -> Group N-1 (if N > 1)
        # Bottom -> Group N+1
        # Rest -> Group N
        
        # We need to consider boundaries (Rank 1 group, Last group)
        # Assuming Group 1 is top.
        
        # Determine total groups in the current round to handle bottom group boundary
        rounds = league_doc.get("rounds", [])
        current_round = next((r for r in rounds if int(r.get("round_id")) == int(round_id)), None)
        
        total_groups = 0
        if current_round:
            total_groups = len(current_round.get("group", []))

        top_player = standings[0]["player"]
        bottom_player = standings[-1]["player"]
        middle_players = [s["player"] for s in standings[1:-1]]
        
        # Helper to add player to next round group
        self.add_player_to_next_round(league_id, next_round_num, current_group_num, middle_players, "stay")
        
        # Handle Top Player (Winner)
        if current_group_num > 1:
            self.add_player_to_next_round(league_id, next_round_num, current_group_num - 1, [top_player], "promote")
        else:
            # Group 1 Winner, stays in Group 1
            self.add_player_to_next_round(league_id, next_round_num, current_group_num, [top_player], "stay")

        # Handle Bottom Player (Loser)
        if current_group_num < total_groups:
             self.add_player_to_next_round(league_id, next_round_num, current_group_num + 1, [bottom_player], "relegate")
        else:
            # Last Group Loser, stays in Last Group
             self.add_player_to_next_round(league_id, next_round_num, current_group_num, [bottom_player], "stay")

    def add_player_to_next_round(self, league_id: str, round_id: int, group_id_num: int, players: list, move_type: str):
        # 1. Fetch League (re-fetch to get latest state or update atomically)
        # Since Mongo array updates can be tricky, we fetch, modify, save or use strict array filters.
        # Using atomic updates is better.
        
        group_id_val = group_id_num
        
        # Ensure Round Exists
        # Ideally we use $addToSet or unique push.
        # Structure: rounds.X.group.Y.players
        
        # If Round doesn't exist, we must create it.
        # If Group doesn't exist, create it.
        
        # Using a specialized Store method is best to avoid concurrency race conditions on the whole document.
        # I Will add `add_players_to_round_group` in PBLeagueStore.
        self.pb_league_store.add_players_to_round_group(league_id, round_id, group_id_val, players)
        
        # After adding, check if that group is full and can be slotted.
        self.check_and_slot_next_round_group(league_id, round_id, group_id_val)

    def check_and_slot_next_round_group(self, league_id: str, round_id: int, group_id: int):
        # Only auto-slot for even round_ids (which means we are generating slots AFTER an odd round)
        if round_id % 2 != 0:
            return

        # Check if group has enough players.
        league_doc = self.pb_league_store.get_league_details(league_id)
        group_size = league_doc.get("group_size", 4) # Default 4
         
        # Find the group
        rounds = league_doc.get("rounds", [])
        target_round = next((r for r in rounds if int(r.get("round_id", -1)) == round_id), None)
        if not target_round: return
        
        # Note: rounds might be dicts or objects depending on pymongo. Store usually returns dicts.
        target_group = next((g for g in target_round.get("group", []) if int(g.get("group_id", -1)) == group_id), None)
        if not target_group: return
        
        # Determine group size: default to league setting, override if group has specific size
        target_size = target_group.get("group_size") or group_size
        
        players = target_group.get("players", [])
        
        # Determine play day and filter out withdrawn players
        play_day = (round_id + 1) // 2
        withdrawals = league_doc.get("withdrawals", [])
        withdrawn_emails = {w["email"] for w in withdrawals if w["play_day"] == play_day}
        active_players = [p for p in players if p.get("email") not in withdrawn_emails]
        
        if len(active_players) >= target_size:
            # Logic to generate matches!
            # We should also check if matches already exist to avoid double slotting.
            if target_group.get("match") and len(target_group["match"]) > 0:
                return # Already slotted
            
            # Generate Matches
            # Re-use slotting logic?
            # For now, simple logic or call a helper.
            new_matches = self.generate_matches_for_group(league_id, round_id, group_id, active_players) # Take top N if > N
            
            # Save Matches to DB
            self.pb_match_store.store_match_details(new_matches)
            
            # Update League Group with Matches
            # We pass everything as objects/dicts?
            # Store needs `SlottingDetailsPayload` or just raw update.
            # Easier to use store method to specifically set matches.
            self.pb_league_store.set_group_matches(league_id, round_id, group_id, new_matches)

    def generate_matches_for_group(self, league_id, round_id, group_id, players):
        from app.vo.pb.match import Match
        from app.vo.pb.team import Team
        import itertools
        from datetime import datetime
        
        matches = []
        # Simple Round Robin for 4 players usually involves specific pairings.
        # 1-2 vs 3-4
        # 1-3 vs 2-4
        # 1-4 vs 2-3
        # I will assume standard pairing for now.
        
        if len(players) == 5:
            # 5 Player Rotation (Everyone plays 4 games, sits 1)
            match_configs = [
                ((0, 1), (2, 3), 4),
                ((0, 2), (1, 4), 3),
                ((0, 3), (2, 4), 1),
                ((0, 4), (1, 3), 2),
                ((1, 2), (3, 4), 0)
            ]
            for idx, ((p1_idx, p2_idx), (p3_idx, p4_idx), sitter_idx) in enumerate(match_configs):
                p1, p2 = players[p1_idx], players[p2_idx]
                p3, p4 = players[p3_idx], players[p4_idx]
                sitter = players[sitter_idx]

                t1 = Team(
                    team_id=f"team_1_{idx}",
                    team_name=f"Team 1", 
                    player_one=p1, 
                    player_two=p2, 
                    score=0
                )
                t2 = Team(
                    team_id=f"team_2_{idx}",
                    team_name=f"Team 2", 
                    player_one=p3, 
                    player_two=p4, 
                    score=0
                )
                
                m = Match(
                    league_id=league_id,
                    league_name="League", # Should get real name
                    round_id=round_id,
                    group_id=group_id,
                    match_id=f"{league_id}-{round_id}-{group_id}-{idx+1}",
                    team_one=t1,
                    team_two=t2,
                    siting_player=sitter,
                    time=datetime.now(), # Placeholder
                    court_number=1,
                    match_status='YetToPlay'
                )
                matches.append(m)
        else:
            # Default to 4 player pairing (standard round robin for 4)
            match_configs = [
                ((0, 1), (2, 3)),
                ((0, 2), (1, 3)),
                ((0, 3), (1, 2))
            ]
            
            for idx, ((p1_idx, p2_idx), (p3_idx, p4_idx)) in enumerate(match_configs):
                if p1_idx >= len(players) or p4_idx >= len(players): continue
                
                p1, p2 = players[p1_idx], players[p2_idx]
                p3, p4 = players[p3_idx], players[p4_idx]
                
                t1 = Team(
                    team_id=f"team_1_{idx}",
                    team_name=f"Team 1", 
                    player_one=p1, 
                    player_two=p2, 
                    score=0
                )
                t2 = Team(
                    team_id=f"team_2_{idx}",
                    team_name=f"Team 2", 
                    player_one=p3, 
                    player_two=p4, 
                    score=0
                )
                
                m = Match(
                    league_id=league_id,
                    league_name="League", # Should get real name
                    round_id=round_id,
                    group_id=group_id,
                    match_id=f"{league_id}-{round_id}-{group_id}-{idx+1}",
                    team_one=t1,
                    team_two=t2,
                    time=datetime.now(), # Placeholder
                    court_number=1,
                    match_status='YetToPlay'
                )
                matches.append(m)
        return matches

    def delete_league(self, league_id: str):
        # 1. Delete associated matches
        self.pb_match_store.delete_matches_by_league(league_id)
        
        # 2. Delete the league
        return self.pb_league_store.delete_league(league_id)