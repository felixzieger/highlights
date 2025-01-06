import yaml
import os


def remove_shorter_duplicates(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    # Dictionary to hold the longest entries
    longest_entries = {}

    for entry in data:
        text = entry["text"]
        page = entry["page"]

        # Check if this text is already in the dictionary
        # If the text is already in the dictionary, compare lengths
        if text not in longest_entries:
            longest_entries[text] = {"text": text, "page": page}
        else:
            # If the current text is longer, replace the existing entry
            if len(text) > len(longest_entries[text]["text"]):
                longest_entries[text] = {"text": text, "page": page}

    # Create a list to hold the filtered data
    filtered_data = []
    seen_texts = set()

    for entry in longest_entries.values():
        text = entry["text"]
        # Check for partial matches
        if not any(text in seen for seen in seen_texts) and not any(
            seen in text for seen in seen_texts
        ):
            filtered_data.append(entry)
            seen_texts.add(text)

    # Write the filtered data back to the file
    with open(file_path, "w", encoding="utf-8") as file:
        yaml.dump(filtered_data, file, allow_unicode=True, sort_keys=False)


if __name__ == "__main__":
    directory_path = "_data/books"
    for filename in os.listdir(directory_path):
        if filename.endswith(".yaml"):
            file_path = os.path.join(directory_path, filename)
            remove_shorter_duplicates(file_path)
            print(
                f"Filtered duplicates in {filename}, keeping only the longest entries."
            )
