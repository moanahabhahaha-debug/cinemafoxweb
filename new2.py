import os
import re
import json
import time
import base64
import requests
from urllib.parse import quote

GITHUB_TOKEN = "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"
GITHUB_USER = "moanahabhahaha-debug"
GITHUB_REPO = "new4"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRANSLATION_DIR = os.path.join(BASE_DIR, "ترجمه")
OUTPUT_FILE = os.path.join(BASE_DIR, "ab.js")

API_BASE = f"https://api.github.com/repos/{GITHUB_USER}/{GITHUB_REPO}"

HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28"
}


def ensure_repository_has_commit():
    response = requests.get(
        API_BASE,
        headers=HEADERS,
        timeout=30
    )

    if response.status_code != 200:
        print("❌ لا يمكن الوصول إلى Repository")
        print(response.status_code)
        print(response.text)
        return False

    repo = response.json()

    if repo.get("size", 0) > 0:
        return True

    print("⚠️ Repository فارغ.")
    print("📄 إنشاء أول Commit...")

    content = "# CinemaFox Subtitles\n"

    encoded = base64.b64encode(
        content.encode("utf-8")
    ).decode("utf-8")

    response = requests.put(
        f"{API_BASE}/contents/README.md",
        headers=HEADERS,
        json={
            "message": "Initialize repository",
            "content": encoded
        },
        timeout=60
    )

    if response.status_code not in (200, 201):
        print("❌ فشل إنشاء Commit")
        print(response.status_code)
        print(response.text)
        return False

    print("✅ تم إنشاء أول Commit.")
    time.sleep(2)

    return True


def make_id(name):
    name = name.strip().lower()

    replacements = {
        "ً": "",
        "ٌ": "",
        "ٍ": "",
        "َ": "",
        "ُ": "",
        "ِ": "",
        "ّ": "",
        "ْ": "",
        "ـ": ""
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    name = re.sub(
        r"[^a-z0-9\u0600-\u06ff]+",
        "_",
        name
    )

    name = re.sub(
        r"_+",
        "_",
        name
    )

    return name.strip("_") or "series"


def get_season_from_folder(folder):
    arabic = {
        "الاول": 1,
        "الأول": 1,
        "الثاني": 2,
        "الثالث": 3,
        "الرابع": 4,
        "الخامس": 5,
        "السادس": 6,
        "السابع": 7,
        "الثامن": 8,
        "التاسع": 9,
        "العاشر": 10
    }

    match = re.search(r"\d+", folder)

    if match:
        return int(match.group())

    for word, number in arabic.items():
        if word in folder:
            return number

    return 1


def get_episode_info(filename, season_folder):
    name = os.path.splitext(filename)[0]

    # S01E01 / s01e01
    match = re.search(
        r"[Ss](\d{1,3})[Ee](\d{1,4})",
        name
    )

    if match:
        return int(match.group(1)), int(match.group(2))

    season = get_season_from_folder(
        season_folder
    )

    patterns = [
        r"[Ee]pisode[\s._-]*(\d+)",
        r"[Ee][Pp][\s._-]*(\d+)",
        r"[Ee][Pp](\d+)",
        r"[Ee](\d+)",
        r"الحلقة[\s._-]*(\d+)",
        r"episode[\s._-]*(\d+)",
        r"ep[\s._-]*(\d+)"
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            name,
            re.IGNORECASE
        )

        if match:
            return season, int(match.group(1))

    # أسماء مثل:
    # 1.vtt
    # 2.vtt
    # 03.vtt
    #
    # نأخذ آخر رقم من الاسم
    numbers = re.findall(
        r"\d+",
        name
    )

    if numbers:
        return season, int(numbers[-1])

    return season, None


def create_release(series_name, season_number):
    safe_id = make_id(series_name)

    tag = (
        f"subtitle-{safe_id}-"
        f"s{season_number}-"
        f"{int(time.time())}"
    )

    name = (
        f"{series_name} - الموسم {season_number}"
    )

    data = {
        "tag_name": tag,
        "name": name,
        "body": (
            f"CinemaFox subtitles\n"
            f"{series_name}\n"
            f"Season {season_number}"
        ),
        "draft": False,
        "prerelease": False
    }

    response = requests.post(
        f"{API_BASE}/releases",
        headers=HEADERS,
        json=data,
        timeout=60
    )

    if response.status_code not in (200, 201):
        print("❌ فشل إنشاء Release")
        print(response.status_code)
        print(response.text)
        return None

    return response.json()


def upload_vtt(release, file_path):
    release_id = release["id"]
    filename = os.path.basename(file_path)

    with open(file_path, "rb") as f:
        content = f.read()

    upload_url = (
        f"https://uploads.github.com/repos/"
        f"{GITHUB_USER}/{GITHUB_REPO}/releases/"
        f"{release_id}/assets"
        f"?name={quote(filename)}"
    )

    headers = {
        "Authorization":
            f"Bearer {GITHUB_TOKEN}",

        "Accept":
            "application/vnd.github+json",

        "Content-Type":
            "application/octet-stream",

        "X-GitHub-Api-Version":
            "2022-11-28"
    }

    response = requests.post(
        upload_url,
        headers=headers,
        data=content,
        timeout=180
    )

    if response.status_code not in (200, 201):
        print(
            f"❌ فشل رفع: {filename}"
        )
        print(
            response.status_code,
            response.text
        )
        return None

    return response.json().get(
        "browser_download_url"
    )


def scan_all():
    result = {}

    if not os.path.isdir(TRANSLATION_DIR):
        print(
            "❌ مجلد ترجمه غير موجود:"
        )
        print(TRANSLATION_DIR)
        return result

    series_list = sorted(
        [
            x for x in os.listdir(
                TRANSLATION_DIR
            )
            if os.path.isdir(
                os.path.join(
                    TRANSLATION_DIR,
                    x
                )
            )
        ],
        key=lambda x: x.lower()
    )

    for series_name in series_list:
        series_path = os.path.join(
            TRANSLATION_DIR,
            series_name
        )

        print("\n" + "=" * 70)
        print("📺", series_name)
        print("=" * 70)

        result[series_name] = {
            "title": series_name,
            "id": make_id(series_name),
            "seasons": {}
        }

        season_list = sorted(
            [
                x for x in os.listdir(
                    series_path
                )
                if os.path.isdir(
                    os.path.join(
                        series_path,
                        x
                    )
                )
            ],
            key=lambda x: (
                get_season_from_folder(x)
            )
        )

        for season_folder in season_list:
            season_path = os.path.join(
                series_path,
                season_folder
            )

            files = [
                x for x in os.listdir(
                    season_path
                )
                if x.lower().endswith(".vtt")
            ]

            episodes = []

            for filename in files:
                season_number, episode_number = (
                    get_episode_info(
                        filename,
                        season_folder
                    )
                )

                if episode_number is None:
                    print(
                        "⚠️ تخطي ملف:",
                        filename
                    )
                    continue

                episodes.append({
                    "season": season_number,
                    "episode": episode_number,
                    "file": os.path.join(
                        season_path,
                        filename
                    ),
                    "filename": filename
                })

            episodes.sort(
                key=lambda x: x["episode"]
            )

            if not episodes:
                continue

            season_number = episodes[0]["season"]

            result[series_name]["seasons"][
                f"season_{season_number}"
            ] = episodes

    return result


def main():
    print("=" * 70)
    print("       CINEMA FOX - ALL SUBTITLES")
    print("=" * 70)

    if GITHUB_TOKEN == "ضع_التوكن_هنا":
        print("❌ ضع التوكن داخل GITHUB_TOKEN")
        input("\nاضغط Enter للخروج...")
        return

    if not ensure_repository_has_commit():
        input("\nاضغط Enter للخروج...")
        return

    all_data = scan_all()

    if not all_data:
        print("❌ لا توجد ملفات VTT.")
        input("\nاضغط Enter للخروج...")
        return

    final_data = {
        "dramas": []
    }

    for series_name, series_data in all_data.items():

        drama = {
            "title": series_data["title"],
            "id": series_data["id"],
            "seasons": {}
        }

        for season_key, episodes in (
            series_data["seasons"].items()
        ):

            season_number = int(
                season_key.replace(
                    "season_",
                    ""
                )
            )

            print("\n" + "-" * 70)
            print(
                f"📺 {series_name}"
            )
            print(
                f"🎬 الموسم {season_number}"
            )
            print(
                f"🔢 عدد الحلقات: {len(episodes)}"
            )
            print("-" * 70)

            release = create_release(
                series_name,
                season_number
            )

            if not release:
                continue

            episode_links = {}

            for item in episodes:

                episode_number = item[
                    "episode"
                ]

                print(
                    f"⬆️ الحلقة {episode_number}: "
                    f"{item['filename']}"
                )

                url = upload_vtt(
                    release,
                    item["file"]
                )

                if url:
                    episode_links[
                        str(episode_number)
                    ] = url

                time.sleep(0.5)

            if episode_links:
                episode_links = dict(
                    sorted(
                        episode_links.items(),
                        key=lambda x:
                            int(x[0])
                    )
                )

                drama["seasons"][
                    season_key
                ] = {
                    "total_episodes":
                        len(episode_links),

                    "episodes":
                        episode_links
                }

        if drama["seasons"]:
            final_data["dramas"].append(
                drama
            )

    final_data["dramas"].sort(
        key=lambda x:
            x["title"].lower()
    )

    js_content = (
        "const subtitlesData = "
        + json.dumps(
            final_data,
            ensure_ascii=False,
            indent=2
        )
        + ";\n"
    )

    with open(
        OUTPUT_FILE,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(js_content)

    print("\n" + "=" * 70)
    print("✅ اكتمل كلشي")
    print("=" * 70)
    print(
        "📄 الملف:",
        OUTPUT_FILE
    )
    print(
        "📺 عدد المسلسلات:",
        len(final_data["dramas"])
    )
    print("=" * 70)

    input("\nاضغط Enter للخروج...")


if __name__ == "__main__":
    main()