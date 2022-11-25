import datetime as dt
import re
import time

import requests
import html5lib
from bs4 import BeautifulSoup
import googleapiclient.discovery
import google.auth


def get_calendar_html(year, month):
    CALURL = "https://syllabus.naist.jp/schedules/preview_monthly"
    text = requests.get(f"{CALURL}/{str(year)}/{str(month)}").text
    return text


def construct_data(html_text, year, month):
    soup = BeautifulSoup(html_text, "html5lib")

    # htmlの書式に則って授業情報の抜き出し
    shedule_table = soup.find("table", attrs={"class": "tbl_m_schedule"})
    tr_classes = shedule_table.find_all("td", id=re.compile('^\d+-\d+-\d+$'))
    tr_class_note_dict = {
        c["id"].rstrip("_note"): c.text.strip()
        for c
        in shedule_table.find_all("td", id=re.compile('^\d+-\d+-\d+_note$'))
        }

    # 開始時間のタプル
    period_starttime = (
        dt.time(9, 20),
        dt.time(11, 0),
        dt.time(13, 30),
        dt.time(15, 10),
        dt.time(16, 50),
        dt.time(18, 30)
        )

    # 抜き出したデータを構造化
    data = []
    for c in tr_classes:
        event_id = c["id"].split("-")
        lines = c.get_text("[!tag]").strip().split("[!tag]") # 区切り文字列を"[!tag]"にして衝突防止
        teachers = ""
        nth = ""
        # 授業名、教室、教員名の抽出 ここは適当なパターンマッチングなので修正の余地あり
        for i in range(len(lines)):
            if i == 0 or i == len(lines):
                continue
            line = lines[i]
            if i == 1:
                title = line
            elif i == 2:
                classroom = line.lstrip("\u3000").strip("[]")
            elif line.startswith("\u3000"):
                line = line.lstrip("\u3000")
                teachers += line
            elif line.startswith("＜第"):
                nth = line
        teachers_list = [t.replace("\u3000", " ").strip(" ") for t in teachers.split("、")]

        # 開始時刻と終了時刻を作成
        date_start = dt.datetime.combine(
            dt.date(year, month, int(event_id[0])),
            period_starttime[int(event_id[1])]
            )
        date_end = date_start + dt.timedelta(hours=1, minutes=30)

        # 辞書にして
        event = {
            "class": title,
            "period": int(event_id[1]), # 時限 (0始まり)
            "starttime": date_start.strftime("%Y-%m-%dT%H:%M:%S"),
            "endtime": date_end.strftime("%Y-%m-%dT%H:%M:%S"),
            "class_number": int(event_id[2]), # 何番目の授業か (IDとは別)
            "classroom": classroom,
            "teachers": teachers_list,
            "note": tr_class_note_dict[c["id"]]
        }
        if nth:
            event["nth"] = nth

        # 格納
        data.append(event)

    return data


def send_events(calendarid_path, key_filename, event_data):
    SCOPES = ['https://www.googleapis.com/auth/calendar']

    with open(calendarid_path, "r") as f:
        calender_id = f.read()

    # Googleの認証情報をファイルから読み込む
    gapi_creds = google.auth.load_credentials_from_file(key_filename, SCOPES)[0]

    # APIと対話するためのResourceオブジェクトを構築する
    service = googleapiclient.discovery.build('calendar', 'v3', credentials=gapi_creds)
    # 予定を書き込む
    # 書き込む予定情報を用意する
    for _ in event_data:
        _teachers = "\n".join(_["teachers"])

        # descriptionテキストの作成
        dsc = f'{_["period"] + 1}限' + "\n"
        if "nth" in _:
            if _["nth"]:
                dsc += _["nth"] + "\n"
        dsc += f'担当教員：' + "\n" + _teachers
        if _["note"]:
            dsc += "\n\n" + _["note"]

        # bodyに格納
        body = {
            'summary': _["class"],
            'location': _["classroom"],
            'description': dsc,
            'start': {
                'dateTime': _["starttime"],
                'timeZone': 'Japan'
                },
            'end': {
                'dateTime': _["endtime"],
                'timeZone': 'Japan'
                }
        }
        # 用意した予定を登録する
        event = service.events().insert(calendarId=calender_id, body=body).execute()
        time.sleep(1.25)


def main():
    import sys
    args_ = sys.argv[1:]
    YEAR, MONTH = int(args_[0]), int(args_[1])
    CALID_PATH, KEYFILE = args_[2:]

    html_text = get_calendar_html(YEAR, MONTH)
    data = construct_data(html_text, YEAR, MONTH)
    send_events(CALID_PATH, KEYFILE, data)


if __name__ == '__main__':
    main()
