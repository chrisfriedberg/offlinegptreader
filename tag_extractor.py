import re
from collections import Counter

# Common system or generic words to ignore
EXCLUDE = {
    'and', 'the', 'that', 'this', 'with', 'from', 'have', 'but', 'for', 'you', 'are', 'was', 'not',
    'has', 'had', 'been', 'were', 'they', 'will', 'would', 'could', 'should', 'can', 'did', 'do',
    'about', 'like', 'just', 'what', 'when', 'where', 'which', 'who', 'how', 'why', 'also', 'some',
    'more', 'than', 'there', 'their', 'then', 'them', 'your', 'into', 'over', 'under', 'such', 'each',
    'only', 'other', 'any', 'very', 'many', 'much', 'even', 'still', 'those', 'these', 'being', 'through'
}

# Minimum times a word must appear to become a tag
FREQUENCY_THRESHOLD = 2
# Maximum number of tags per conversation
MAX_TAGS = 10


def extract_tags(text: str) -> list:
    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_\-]{2,}\b', text.lower())
    counts = Counter(word for word in words if word not in EXCLUDE)
    common = counts.most_common(MAX_TAGS)
    return [tag for tag, _ in common if counts[tag] >= FREQUENCY_THRESHOLD]
