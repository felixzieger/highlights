import yaml
import os
import re
import subprocess


def get_new_yaml_files(directory_path):
    """Return set of YAML filenames that are untracked by git (newly created)."""
    try:
        result = subprocess.run(
            ["git", "ls-files", "--others", "--exclude-standard", directory_path],
            capture_output=True,
            text=True,
            check=True,
        )
        untracked = {
            os.path.basename(f)
            for f in result.stdout.strip().split("\n")
            if f.endswith(".yaml")
        }
    except subprocess.CalledProcessError:
        untracked = set()

    return untracked


def extract_page_number(page_str):
    # Extract the first number from the page string
    match = re.search(r"\d+", page_str)
    if match:
        return int(match.group())
    return float("inf")  # Return infinity for pages without numbers


def is_fragment(text):
    """Detect if a highlight text is a broken/accidental Kindle clipping fragment.

    Catches common Kindle clipping artifacts:
    - Dangling quotation marks from imprecise highlight selection
    - Very short meaningless snippets (single words, headings)
    - Text that clearly cuts off mid-phrase (ends with function word)
    - Text starting/ending with structural breaks (brackets, comma endings)

    Returns True if the text appears to be a fragment, False otherwise.
    Tuned for high precision (few false positives) at the cost of some recall.
    """
    text = text.strip()
    if not text:
        return True

    # --- Helpers ---
    terminal_chars = set(".!?\u201d\u2019\"\u2018')\u2014\u2013]")
    ends_cleanly = text[-1] in terminal_chars

    opening_chars = set("\"'(\u201c\u201e\u2018\u00ab")
    first_alpha = next((c for c in text if c.isalpha()), "")
    starts_mid = first_alpha and first_alpha.islower() and text[0] not in opening_chars

    # 1. Very short with no sentence punctuation (single words, headings)
    if len(text) < 30 and not re.search(r"[.!?]", text):
        return True

    # 2. Dangling open quote near end: 'some text. \u201cDid'
    if re.search(r'[\u201c"]\s*\w{1,15}$', text):
        return True

    # 3. Dangling short word after sentence-ending punctuation: '...tell you. He'
    if re.search(r'[.!?"\u201d]\s+[A-Z]\w{0,15}$', text):
        return True

    # 4. Starts with closing bracket
    if text[0] in (")", "]", "}"):
        return True

    # 5. Starts with opening paren and doesn't end cleanly
    if text[0] == "(" and not ends_cleanly:
        return True

    # 6. Ends with a function/cutoff word — strongest signal of mid-sentence cutoff
    cutoff_re = (
        r"\s+(a|an|the|of|to|in|for|on|at|by|and|or|but|is|isn't|aren't|"
        r"was|were|wasn't|weren't|not|with|from|into|no|that|which|when|"
        r"where|who|whose|how|if|as|its|than|then|yet|so|also|just|even|"
        r"still|only|very|more|most|much|many|own|such|each|all|both|few|"
        r"other|some|any|every|what|whether|because|although|unless|until|"
        r"since|while|after|before|during|about|over|under|between|through|"
        r"against|upon|across|without|within|behind|along|around|up|down|"
        r"out|off|back|like|near|past|per|plus|via|do|does|did|has|have|"
        r"had|may|might|must|shall|should|will|would|can|could|need|ought)$"
    )
    if re.search(cutoff_re, text, re.IGNORECASE):
        return True

    # 7. Ends with comma
    if text[-1] == ",":
        return True

    # 8. Ends with colon and text is substantial (not just a label)
    if text[-1] == ":" and len(text) > 40:
        return True

    # 9. Starts mid-sentence AND ends without terminal punctuation (long texts only)
    if starts_mid and not ends_cleanly and len(text) > 120:
        return True

    return False


def remove_shorter_duplicates(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not data:
        return

    # Dictionary to hold the longest entries
    longest_entries = {}

    # First pass: collect all entries
    for i, entry in enumerate(data):
        # Skip entries missing required fields
        if not isinstance(entry, dict) or "text" not in entry or "page" not in entry:
            continue

        text = entry["text"]
        page = entry["page"]

        # Store all entries with their text as key, including their original position
        longest_entries[text] = {"text": text, "page": page, "original_index": i}

    # Second pass: find the longest version of overlapping texts
    filtered_data = []
    processed_texts = set()

    # Sort entries by length in descending order to process longest first
    sorted_entries = sorted(
        longest_entries.values(), key=lambda x: len(x["text"]), reverse=True
    )

    for entry in sorted_entries:
        text = entry["text"]

        # Skip if this text is already contained within a longer text we've processed
        if any(text in processed for processed in processed_texts):
            continue

        # Add this text to processed texts
        processed_texts.add(text)
        filtered_data.append(entry)

    # Sort the filtered data by original position
    filtered_data.sort(key=lambda x: x["original_index"])

    # Remove the original_index before writing to file
    for entry in filtered_data:
        del entry["original_index"]

    # Write the filtered data back to the file
    with open(file_path, "w", encoding="utf-8") as file:
        yaml.dump(filtered_data, file, allow_unicode=True, sort_keys=False)


def remove_fragments(file_path):
    """Remove broken/accidental Kindle clipping fragments from a YAML file.

    Returns a list of removed fragment texts for logging.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not data:
        return []

    kept = []
    removed = []

    for entry in data:
        if not isinstance(entry, dict) or "text" not in entry:
            kept.append(entry)
            continue

        if is_fragment(entry["text"]):
            removed.append(entry["text"])
        else:
            kept.append(entry)

    if removed:
        with open(file_path, "w", encoding="utf-8") as file:
            yaml.dump(kept, file, allow_unicode=True, sort_keys=False)

    return removed


if __name__ == "__main__":
    directory_path = "_data/books"
    new_files = get_new_yaml_files(directory_path)

    if not new_files:
        print("No new (untracked) YAML files to deduplicate.")
    else:
        print(f"Found {len(new_files)} new file(s) to deduplicate.")

    for filename in sorted(new_files):
        file_path = os.path.join(directory_path, filename)
        remove_shorter_duplicates(file_path)
        print(f"Filtered duplicates in {filename}, keeping only the longest entries.")

        removed = remove_fragments(file_path)
        if removed:
            print(f"Removed {len(removed)} fragment(s) from {filename}:")
            for text in removed:
                print(f"  - {text[:80]}{'...' if len(text) > 80 else ''}")

    existing_count = len(
        [f for f in os.listdir(directory_path) if f.endswith(".yaml")]
    ) - len(new_files)
    if existing_count > 0:
        print(f"Skipped {existing_count} existing file(s) already tracked in git.")
