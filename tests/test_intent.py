from channels.email.intent_classifier import IntentClassifier

classifier = IntentClassifier()

email = """
"Hi,
I’m planning to replace an old toilet in my home.
Could you tell me what the typical installation cost would be, and whether disposal of the old unit is included?
Best,
Isabella Martin"
"""

result = classifier.predict_intent(email)

print("Predicted Intent:", result["intent"])
print("Confidence:", result["confidence"])
