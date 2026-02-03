def analyze_sentiment(text: str) -> dict:
    # Mock sentiment analysis
    anxiety_keywords = [
        "hurt",
        "pain",
        "scared",
        "nervous",
        "needle",
        "recovery",
        "downtime",
    ]
    is_anxious = any(k in text.lower() for k in anxiety_keywords)
    return {"is_anxious": is_anxious, "score": 0.9 if is_anxious else 0.1}


def empathy_guardrail(text: str):
    sentiment = analyze_sentiment(text)
    if sentiment["is_anxious"]:
        return "I completely understand your concern. Patient comfort is our absolute priority. We use a medical-grade numbing protocol and offer Pro-Nox (laughing gas) to ensure you feel at ease. Would you like to see our comfort menu?"
    return None
