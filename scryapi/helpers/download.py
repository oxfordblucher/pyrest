from pathlib import Path
import requests
import json

dl_folder = Path(__file__).resolve().parent.parent / "data"
dl_folder.mkdir(exist_ok=True)
dl_file_path = dl_folder / "card_data.json"


def get_link():
    try:
        raw_api_data = requests.get("https://api.scryfall.com/bulk-data/oracle_cards")
        raw_api_data.raise_for_status()

        parsed_data = json.loads(raw_api_data.text)
        return parsed_data["download_uri"]

    except requests.exceptions.RequestException as e:
        print(f"Error fetching data: {e}")
        return None


def download():
    dl_link = get_link()
    if dl_link:
        try:
            res = requests.get(dl_link, stream=True)
            res.raise_for_status()

            with open(dl_file_path, "wb") as f:
                for chunk in res.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print("File downloaded successfully.")

        except requests.exceptions.RequestException as e:
            print(f"Failed to download file: {e}")


if __name__ == "__main__":
    download()
