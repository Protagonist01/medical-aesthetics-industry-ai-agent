"""
Empathy Guardrail Module
Detects user anxiety and provides reassuring responses.
"""


def analyze_sentiment(text: str) -> str:
    """Quick sentiment analysis using keyword detection."""
    anxiety_keywords = ["scared", "nervous", "afraid", "worried", "anxious", "pain", "hurt"]
    text_lower = text.lower()
    for keyword in anxiety_keywords:
        if keyword in text_lower:
            return "anxious"
    return "neutral"


def empathy_guardrail(user_message: str) -> str:
    """Check if user needs empathetic response before proceeding."""
    sentiment = analyze_sentiment(user_message)
    if sentiment == "anxious":
        return (
            "I completely understand your concerns - it's totally natural to feel that way! "
            "Our Comfort Protocol includes numbing cream, Pro-Nox (laughing gas), and "
            "gentle techniques that most clients say make the experience much easier than expected. "
            "Would you like to know more about how we keep you comfortable?"
        )
    return None
