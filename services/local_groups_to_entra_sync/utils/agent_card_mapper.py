def map_local_agent_card_to_entra_manifest(local_card: dict) -> dict:
    """
    Maps a local A2A agent card to a Microsoft Graph agentCardManifest-compatible dict.
    Ref: https://learn.microsoft.com/en-us/graph/api/resources/agentcardmanifest?view=graph-rest-beta
    """
    skills = [
        {
            "id": skill["id"],
            "displayName": skill["name"],
            "description": skill.get("description"),
            "tags": skill.get("tags", []),
            "examples": skill.get("examples", []),
            "inputModes": skill.get("inputModes", []),
            "outputModes": skill.get("outputModes", []),
        }
        for skill in local_card.get("skills", [])
        if skill.get("is_enabled", True)
    ]

    return {
        "displayName": local_card["name"],
        "description": local_card.get("description"),
        "version": local_card.get("version"),
        "protocolVersion": local_card.get("protocolVersion"),
        "defaultInputModes": local_card.get("defaultInputModes", []),
        "defaultOutputModes": local_card.get("defaultOutputModes", []),
        "capabilities": {
            "streaming": local_card.get("capabilities", {}).get("streaming", False),
        },
        "skills": skills,
    }
