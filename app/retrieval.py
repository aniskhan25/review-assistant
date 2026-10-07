"""Small local BM25 index with section preference; no embedding downloads."""

import math
import re
from collections import Counter


def tokens(text):
    return re.findall(r"[\w-]+", text.lower())


def retrieve(evidence, question, limit=5):
    if not evidence:
        return []
    bags = [Counter(tokens(e["text"])) for e in evidence]
    lengths = [sum(b.values()) for b in bags]
    average = sum(lengths) / len(lengths) or 1
    query = set(tokens(" ".join(question["keywords"])))
    frequency = {word: sum(word in bag for bag in bags) for word in query}
    ranked = []
    for ev, bag, length in zip(evidence, bags, lengths):
        score = 0.0
        for word in query:
            tf = bag[word]
            idf = math.log(1 + (len(bags) - frequency[word] + 0.5) / (frequency[word] + 0.5))
            score += idf * tf * 2.5 / (tf + 1.5 * (0.25 + 0.75 * length / average))
        section_match = any(s in ev["section"].lower() for s in question["sections"])
        if score or section_match:
            ranked.append((score + 1.5 * section_match, ev))
    ranked.sort(key=lambda item: (-item[0], item[1]["id"]))
    return [dict(ev, retrieval_score=round(score, 4)) for score, ev in ranked[:limit]]
