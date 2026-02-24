
try:
    # Case 1: String group_size
    target_group = {"group_size": "5"}
    group_size = 4
    target_size = target_group.get("group_size") or group_size
    print(f"Case 1 target_size: {target_size} (type: {type(target_size)})")
    if 5 >= target_size:
        print("Case 1 comparison success")
except Exception as e:
    print(f"Case 1 failed: {e}")

try:
    # Case 2: None group_size (from league) and missing in group
    target_group = {}
    group_size = None 
    target_size = target_group.get("group_size") or group_size
    print(f"Case 2 target_size: {target_size} (type: {type(target_size)})")
    if 5 >= target_size:
         print("Case 2 comparison success")
except Exception as e:
    print(f"Case 2 failed: {e}")
