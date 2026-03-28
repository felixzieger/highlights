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

    existing_count = len(
        [f for f in os.listdir(directory_path) if f.endswith(".yaml")]
    ) - len(new_files)
    if existing_count > 0:
        print(f"Skipped {existing_count} existing file(s) already tracked in git.")
