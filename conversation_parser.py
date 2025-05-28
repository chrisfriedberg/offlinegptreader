import os
import sys
import json
import csv
import hashlib
from datetime import datetime

EXPORT_DIR = "markdown_exports"
INDEX_CSV = "feralcat_index.csv"
LOG_PATH = "feralcat_log.txt"

def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(f"{timestamp} {message}\n")

def extract_messages(convo):
    messages = []
    for node in convo.get("mapping", {}).values():
        if not isinstance(node, dict):
            continue
        message = node.get("message")
        if not message:
            continue
        content_block = message.get("content")
        if isinstance(content_block, dict):
            parts = content_block.get("parts", [])
            if isinstance(parts, list):
                messages.extend(parts)
            elif isinstance(parts, str):
                messages.append(parts)
        elif isinstance(content_block, str):
            messages.append(content_block)
    return messages

def safe_filename(s):
    return "".join(c for c in s if c not in r'\/:*?"<>|').strip()

def load_existing_tags():
    tags_by_filename = {}
    if os.path.exists(INDEX_CSV):
        with open(INDEX_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row["title"]
                filename = row["filename"]
                tags = [word for word in title.split() if word.startswith("#")]
                tags_by_filename[filename] = tags
    return tags_by_filename

def file_hash(path):
    if not os.path.exists(path):
        return None
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()

def compute_message_hash(messages):
    clean = [m if isinstance(m, str) else json.dumps(m, sort_keys=True) for m in messages]
    return hashlib.sha1("".join(clean).encode("utf-8")).hexdigest()

def main():
    if len(sys.argv) < 2:
        print("❌ No input file provided. Usage: python conversation_parser.py <path_to_conversations.json>")
        log("❌ Parser run failed — No input file provided.")
        return

    json_path = sys.argv[1]

    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    existing_tags = load_existing_tags()
    index_rows = []

    updated_content = 0
    new_count = 0

    preserved_tags_log = []
    merged_tags_log = []

    for convo in data:
        title = convo.get("title", "Untitled Conversation").strip()
        date_str = convo.get("create_time")
        if date_str:
            try:
                if isinstance(date_str, (int, float)):
                    dt = datetime.fromtimestamp(date_str)
                else:
                    dt = datetime.fromisoformat(date_str)
                date = dt.strftime("%Y-%m-%d")
            except Exception:
                date = "unknown"
        else:
            date = "unknown"

        filename = f"{date} - {safe_filename(title)}.md"
        filepath = os.path.join(EXPORT_DIR, filename)

        old_tags = set(existing_tags.get(filename, []))
        title_wo_tags = " ".join(part for part in title.split() if not part.startswith("#"))

        messages = extract_messages(convo)
        clean_messages = [m if isinstance(m, str) else json.dumps(m, sort_keys=True) for m in messages]
        new_msg_hash = compute_message_hash(messages)

        final_tags = sorted(old_tags)
        final_title = f"{title_wo_tags} {' '.join(final_tags)}".strip()
        new_md_content = f"# {final_title}\n\n" + "\n\n".join(clean_messages)
        new_file_hash = hashlib.sha1(new_md_content.encode("utf-8")).hexdigest()
        existing_file_hash = file_hash(filepath)

        should_write = True

        if os.path.exists(filepath):
            if new_file_hash != existing_file_hash:
                if compute_message_hash(messages) != new_msg_hash:
                    updated_content += 1
                elif final_tags:
                    preserved_tags_log.append(f"    - {filename} → {' '.join(final_tags)}")
            else:
                should_write = False
        else:
            new_count += 1

        if filename in existing_tags:
            old_in_title = set(existing_tags[filename])
            new_in_title = set(final_tags)
            newly_added = new_in_title - old_in_title
            if newly_added:
                merged_tags_log.append(f"    - {filename} → added: {' '.join(sorted(newly_added))}")

        if should_write:
            with open(filepath, "w", encoding="utf-8") as md_file:
                md_file.write(new_md_content.strip())

        word_count = len(new_md_content.split())
        index_rows.append({
            "title": final_title,
            "date": date,
            "filename": filename,
            "word_count": word_count
        })

    with open(INDEX_CSV, "w", encoding="utf-8", newline="") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=["title", "date", "filename", "word_count"])
        writer.writeheader()
        for row in index_rows:
            writer.writerow(row)

    skipped = len(data) - new_count

    log(f"✅ Parsed {len(data)} conversations from {os.path.basename(json_path)}")
    log(f"1. Total files imported: {len(data)}")
    log(f"2. Original: {len(preserved_tags_log)} tags found and preserved")
    for entry in preserved_tags_log:
        log(entry)
    log(f"3. Updated: {len(merged_tags_log)} tags found and merged")
    for entry in merged_tags_log:
        log(entry)
    log(f"4. New files added: {new_count}")
    log(f"5. Skipped (no changes): {skipped}")

if __name__ == "__main__":
    main()
