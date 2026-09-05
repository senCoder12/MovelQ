"""Insight-scoped conversation.

Not a Q&A box over the dataset: every answer is assembled from figures that
were already computed for one InsightPacket. The model's only job is to say
which of eight questions was asked and with what slots -- see
app/chat/router.py. It never computes a number, never writes SQL, and never
answers from general knowledge; anything outside the eight is refused by
name (app/chat/intents.py::OUT_OF_SCOPE).
"""
