def parse_follower(user, source_username):
    """Turn one user dict from Instagram's followers API into a flat row."""
    return {
        "id": str(user.get("pk") or user.get("id", "")),
        "username": user.get("username", ""),
        "full_name": user.get("full_name", ""),
        "is_private": bool(user.get("is_private")),
        "is_verified": bool(user.get("is_verified")),
        "profile_url": f"https://www.instagram.com/{user.get('username', '')}/",
        "profile_pic_url": user.get("profile_pic_url", ""),
        "source_username": source_username,
    }


def parse_followers(users, source_username):
    return [parse_follower(user, source_username) for user in users]
