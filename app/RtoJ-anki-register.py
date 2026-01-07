from bs4 import BeautifulSoup
import json
from natasha import MorphVocab, Doc, Segmenter, NewsEmbedding, NewsMorphTagger
import os
import psutil
from random import randint, choice, uniform
import re
import requests
import subprocess
from time import sleep
from urllib.parse import quote

wordlist = set()
config = {
    "lang": "JP", # Ankiの言語設定に合わせてください (デフォルト：日本語)
    "anki_path": None, # Anki.exeの絶対パスを指定 (必須ではない)
    "EN": {"front": "Front", "back": "Back", "modelName": "Basic"}, # Ankiの言語設定が英語ならこちら
    "JP":{"front": "表面", "back": "裏面", "modelName": "基本"}, # Ankiの言語設定が日本語ならこちら
    "deck_name": [], # 自分が使っているデッキ名 (起動時に自動で入力されます)
    "deck_num":  1, # 使用するデッキの番号(1, 2, 3...)
    "input_file": None, # 設定したファイルから入力を受け取る
    "output_file": os.path.join(os.path.dirname(__file__), "unfound_words.txt"), # 見つからなかった単語を出力するファイル
}
"""
基本設定(デフォルト)
初回起動時に設定します。書き換える必要はありません。
"""

"""
発見済み・未解決のバグ(対応策など)
1. 一部の単語が、更新箇所が無いにも関わらず更新するか確認される (更新するかどうかを毎回選択してください)
2. 辞書内の例文に不要ハイフン付きの表記がある場合に、それが残ってしまう (人称変化などの表記と区別できないため手動で修正してください)
"""

Help = """
～～ヘルプ～～
使用時は事前に Anki を起動しておく必要があります。設定すれば自動起動させることもできます。

モード一覧(デフォルト := 空文字 + ENTER)：

1. <単語登録モード>
f : ファイルから読み込み (file)
    config 内で input_file に指定したファイル(.txt, .mdなど)から全てのロシア語を抜き出して読み込む。

i : キーボード入力から読み込み (input)
    キーボード入力で読み込まれた単語または文を読み込む。空文字を送ると終了。
    単語の変化形が含まれている場合は、そこに含まれる単語の原形を推測する。
    最初の改行文字までを扱うため、改行が含まれる文章はあらかじめ詰めておく必要がある。
    文脈の無い単語の変化形を入力すると誤推測の可能性あり。(例えばтестеはтест(テスト), тесто(パンなどの生地), тесть(舅)のいずれの可能性もある)

p : 部分一致検索して登録 (partial match)
    入力した文字列を部分文字列に持つ単語を調べる。
    「カードにしますか？」に対して「y」と入力すると、意味を1, 2つずつまとめたカードを作成する。

r : コトバンクからランダム抽出 (random)
    コトバンクに収録されている語をランダムに抽出する。
    このモードでは「追加するカード枚数」「クイックモードにするか」を求められる。
    追加するカード枚数：ランダムに抽出する単語の数
    クイックモード(デフォルトでY)：y → 単語の意味を確認せずに追加する。
                                n → 単語が追加されるたびに意味を確認するか尋ねられる。

o : unfound_wordsを整理する (organize)
    見つからなかった単語が出力されるunfound_wordsを読み込んで、単語の重複を省き、整列して再びunfound_wordsに出力する。
    その際にコトバンクに見つかった単語はAnkiに登録される。

b : 戻る (back)
    モード選択へ戻る。

2. <その他>
c : カードを追加するデッキを変更する (change deck)  
    カードを追加する先のデッキを変更する。

s : 設定の確認/変更 (setting)
    現在の設定を確認/変更できる。
    「言語」「Ankiのパス」「言語に応じたフィールド名」「デッキ名」
    「選択中のデッキ番号」「読み込むファイルのパス」「出力先のファイルのパス」
    が確認できる。
    設定の変更をする場合、初期設定で入力する全ての項目について設定し直すことができる。

b : 戻る (back)
    モード選択へ戻る。

3. <やめる>
q : やめる (quit)
プログラムを終了する。
                            
～～仕様～～
ロシア語の入力に対して正規化処理(小文字化、記号除去など)を行います。そのため、人名などの大文字で始まる単語には対応していません。
ロシア語以外の入力は無視されます。特に、読み込みファイルに日本語のメモ書きなどが含まれていても大丈夫です。
追加されるカードには、"表面" に「入力された単語」、"裏面" に「単語の意味および用例」がそれぞれ書き込まれます。
"表面" の単語はアクセント位置を赤文字にしています。
単語の意味および用例は "コトバンク -プログレッシブロシア語辞典(露和編)-" よりスクレイピングして取得しています。
短時間に大量のリクエストをすることによるスクレイピング先への過剰なサーバー負荷を避けるため、平均3秒のランダムな待機時間を設定しています。
何らかの理由により見つからなかった単語は、プログラムの実行場所と同じディレクトリにファイルを生成してそこに書き込みます。そこに出力された単語はこのプログラムで対応できないので、自分で意味を調べてください。


～～注意事項・お願い～～
より快適な利用のための改造は基本的に自由にできますが、「sleep(uniform(2, 4))を削除する」「ウイルスを仕込む」など、他人に迷惑がかかる改造はおやめください。
上記が守られなかった場合に生じた問題において、原作者であるnasu(https://github.com/Nasu726)は一切責任を負いません。

～～その他～～
バグや不具合の報告は GitHub (https://github.com/Nasu726/) または 
"""

##############################################################################################################
# Config に関する部分

# 複数の関数で横断して使用するためグローバルで定義
lang = config["lang"] 
deck_num = config["deck_num"]-1

# モジュールの準備
morph_vocab = MorphVocab()
segmenter = Segmenter()
emb = NewsEmbedding()
morph_tagger = NewsMorphTagger(emb)

def Get_Anki_Path():
    """
    Anki のパスを検索して取得する関数
    """
    directory=r"C:\Users"
    extensions=".exe"
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith(extensions):
                file_path = os.path.join(root, file)
                if file_path.split("\\")[-1].strip() == "anki.exe":
                    return file_path
    return None

def Set_Lang():
    """
    Anki の言語を選んで登録する関数
    """
    langs = ["EN", "JP"]
    print("1：English")
    print("2：日本語")
    lang_num = input("言語を選んでください(数字を入力)： ")
    if is_number(lang_num):
        if int(lang_num) <= len(langs):
            config["lang"] = langs[int(lang_num)-1]
            Write_Config()
            print("----------------------------------") # 次の設定の指示を読みやすくするための区切り線
            return True
        else:
            input("有効な数字を選んでください")
            return False
    else:
        input("数字を入力してください")
        return False

def Set_Anki_Path():
    """
    Anki の実行ファイルのパスを設定する関数
    """
    print("Anki のパスを登録します") 
    print("登録することで、Ankiが起動していない場合に自動で起動させることができます")
    print("登録しなくても、事前にAnki を起動しておくことで利用できます")
    print("---------モード一覧---------")
    print("   a：自動検索モード")
    print("skip：スキップする")
    mode = input("モードを選んでください： ")
    if mode == "a":
        print("anki.exe のパスを検索します。検索には長時間かかることがあります")
        anki_path = Get_Anki_Path()
        if anki_path is None:
            input("パスが見つかりませんでした") # 次の設定の指示を読みやすくするための区切り線
            print("----------------------------------") # 次の設定の指示を読みやすくするための区切り線
            return False
        else:
            print("パスが見つかりました")
            config["anki_path"] = anki_path 
            Write_Config()
            print("----------------------------------") # 次の設定の指示を読みやすくするための区切り線
            return True
    elif mode == "skip":
        print("Anki のパスの設定をスキップしました")
        print("----------------------------------") # 次の設定の指示を読みやすくするための区切り線
        return True
    elif os.path.exists(anki_path):
        config["anki_path"] = anki_path 
        Write_Config()
        print("----------------------------------") # 次の設定の指示を読みやすくするための区切り線
        return True
    else:
        input("入力されたパスは正しくないようです")
        return False

def Set_Input_File():
    """
    config における input_file の設定を行う関数
    """
    print("ファイル読み込みに使うファイルを選んでください")
    print("登録することでファイル読み込み機能が利用できます")
    input_file_path = input("ファイルパスを入力(skip でスキップ)： ")
    if input_file_path == "skip":
        print("読み込みファイルのパスの設定をスキップしました")
        print("----------------------------------") # 次の設定の指示を読みやすくするための区切り線
        return True
    elif os.path.exists(input_file_path):
        config["input_file"] = input_file_path
        Write_Config()
        return True
    else:
        print("そのようなファイルは存在しません")
        s = input("設定をスキップしますか？(Y/n)： ")
        if s == "Y":
            print("読み込みファイルのパスの設定をスキップしました")
            print("----------------------------------") # 次の設定の指示を読みやすくするための区切り線
            return True
        else:
            return False


def Set_Config(setting_progress):
    """
    設定を変更する関数
    """
    while True:
        if setting_progress == 0:
            if Set_Lang():
                setting_progress = 1
        elif setting_progress == 1:
            if Set_Anki_Path():
                setting_progress = 2
        elif setting_progress == 2:
            if Set_Input_File():
                setting_progress = 3        
        elif setting_progress == 3:
            if Change_Deck():
                setting_progress = 4
        else:
            input("設定が完了しました(Enterでモード選択へ)")
            break
    return True

def Write_Config():
    """
    設定をjsonファイルに書き込む関数
    """
    path = os.path.join(os.path.dirname(__file__), "config.json")
    with open(path, "w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=4)
    return True

def Read_Config():
    """
    設定をjsonファイルから読み込む関数
    """
    global config, lang, deck_num
    path = os.path.join(os.path.dirname(__file__), "config.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as file:
            config = json.load(file)
    else:
        print("初期設定をします(後から変更できます)")
        Set_Config(0)
        input("ようこそ！")
    
    lang = config["lang"] 
    deck_num = config["deck_num"]-1

    return config

def Check_Config():
    """
    現在の設定を確認する関数
    """
    print("\n現在の設定")
    for key, value in config.items():
        print(f"{key}: {value}")
    return True

##############################################################################################################
# Anki 操作に関する部分

def Anki_is_Running(requestJson):
    """
    Anki が起動しているかどうかを調べる関数
    """
    try:
        response = requests.post("http://127.0.0.1:8765", data=requestJson).json()
        return True, response
    except requests.exceptions.ConnectionError:
        return False, None

def Kill_Anki_Process():
    """
    Anki のプロセスを終了する関数
    """
    anki_proc = None
    for proc in psutil.process_iter(attrs=["name", "exe", "pid"]):
        if proc.info["name"] and "anki.exe" in proc.info["name"].lower():
            if proc.info["exe"] and config["anki_path"].lower() in proc.info["exe"].lower():
                anki_proc = proc
                break
    if anki_proc is not None and Anki_is_Running:
        try:
            anki_proc.terminate()
            anki_proc.wait(timeout=5)
        except psutil.TimeoutExpired:
            anki_proc.kill()
    return True

def anki_connect_request(action, **params):
    """
    AnkiConnectにリクエストを送信する関数
    """
    requestJson = json.dumps({"action": action, "version": 6, "params": params})
    try:
        response = requests.post("http://127.0.0.1:8765", data=requestJson).json()
    except requests.exceptions.ConnectionError:
        if config["anki_path"] is not None:
            print("Ankiを起動します")
            anki_path = config["anki_path"]
            with open(os.devnull, "w") as devnull:
                subprocess.Popen(f'start /min "" "{anki_path}"', shell=True)
                
            for _ in range(10):
                sleep(2)
                running, res = Anki_is_Running(requestJson=requestJson)
                if running:
                    response = res
                    break
        else:
            print("Anki が起動されていません")
            key = input("Anki はインストールされていますか？(Y/n)： ")
            if key == "Y":
                print("Ankiを起動してください")
                exit(0)
            else:
                print(f"Anki をインストールしてください\nインストールはこちらから：https://apps.ankiweb.net/")
                exit(0)

    if not isinstance(response, dict):
        raise Exception("response has an unexpected number of fields")
    if "error" not in response:
        raise Exception("response is missing required error field")
    if "result" not in response:
        raise Exception("response is missing required result field")
    if response["error"] is not None:
        raise Exception(response["error"])
    return response["result"]

##############################################################################################################
# デッキ操作に関する部分

def Get_Deck_Name():
    """
    デッキの名前一覧を取得する関数
    """
    deck_names = anki_connect_request("deckNames")
    return deck_names

def Get_Deck_Version():
    """
    Anki Connect のバージョン情報を取得する関数
    """
    version = anki_connect_request("version")
    print(f"AnkiConnectのバージョン: {version}")
    return

def Change_Deck():
    """
    カードの登録先デッキを変更する関数
    """
    global deck_num
    decks = Get_Deck_Name()
    for i, deck in enumerate(decks):
        print(f"{i+1}: {deck}")
    print(f"現在選択中のデッキは「{decks[deck_num]}」です")
    num = input("カードを登録するデッキ番号を入力してください (0 で変更をキャンセル)： ")
    if is_number(num):
        num = int(num)
        if num == 0:
            input("デッキ変更をキャンセルしました")
            return True
        elif num <= len(decks):
            config["deck_num"] = int(num)
            deck_num = int(num)-1
            Write_Config()
            return True
        else:
            input("入力された番号は有効ではありません。デッキ変更をキャンセルしました")
            return True
    else:
        input("数字以外が入力されました。変更をキャンセルします")
        return True

##############################################################################################################
# 単語読み込みに関する部分

def Read_File():
    """
    読み込みファイルから単語を抜き出してリストにする関数
    """
    russian_words = []

    with open(config["input_file"], "r", encoding="utf-8") as file:
        for line in file.readlines():
            if len(line)==0:
                continue
            russian_words_in_line = Normalize_Text(line)
            # normalized_line = re.sub(r"\(.+\)", "", line).lower()
            # russian_words_in_line = " ".join(re.findall(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*", normalized_line))
            russian_words.extend(Text_to_Wordlist(russian_words_in_line))
    return russian_words

def Random_Pick_Word():
    """
    コトバンクに載っている言葉からランダムに一つ選んで返す関数
    """
    page_number = randint(1,644)
    url = ""
    if page_number == 1:
        url = f"https://kotobank.jp/dictionary/prj/"
    else:
        url = f"https://kotobank.jp/dictionary/prj/{page_number}/"
    response = requests.get(url)
    response.encoding = "utf-8"
    page = BeautifulSoup(response.text, "html.parser")

    # 選ばれたページから単語を抜き出して返す。単語が格納されているタグを探し、random.choice() を使って選ぶ。
    words_list = page.find("section", class_="list")
    words_list = words_list.find_all("li")
    words = []
    for word in words_list: 
        words.append(word.select("span")[0].text)

    word = choice(words)
    return word

def Output_Unfound(unfound_words):
    """
    見つからなかった単語を unfound_words.txt に書き込む関数
    """
    unfound_words = sorted(set(unfound_words))
    if config["input_file"] == config["output_file"]:
        with open(config["output_file"], "w", encoding="utf-8") as file:
            for unfound_word in unfound_words:
                print(unfound_word)
                file.write(f"{unfound_word}\n")
            file.write("--------------------------------------END\n")
    else:
        with open(config["output_file"], "a", encoding="utf-8") as file:
            for unfound_word in unfound_words:
                print(unfound_word)
                file.write(f"{unfound_word}\n")
            file.write("--------------------------------------END\n")
    print(f"見つからなかった単語は{config['output_file'].split("\\")[-1].strip()}に出力されました")

##############################################################################################################
# 表記管理に関する部分

def is_number(num):
    """
    引数が数字のみで構成されているか調べる関数
    """
    return re.fullmatch(r"[0-9]+", num) is not None

def is_russian(word):
    """
    引数がロシア語のアルファベット（А-Я、а-я、Ёё）およびハイフン(-)だけで構成されているかどうか調べる関数
    """
    return re.fullmatch(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*", word) is not None

def Normalize_Text(text):
    """
    文の表記を統一する関数
    """
    #  ()～　の形式になっている語は～だけを取り出す。
    normalized_text = re.sub(r"\(([а-яА-ЯЁё])+\)", "", text)
    # ロシア語としてあり得る文字列のみを抜き出すし、空白区切りで連結
    russian_words_in_text = " ".join(re.findall(r"[А-Яа-яЁё]+(?:-[А-Яа-яЁё]+)*", normalized_text))
    # 小文字に統一する
    text = russian_words_in_text.lower()
    return text

##############################################################################################################
# 単語カード追加のための準備に関する部分

def Get_Imp_Form(perf):
    """
    完了体動詞を不完了体動詞にする関数
    """
    url = f"https://en.openrussian.org/ru/{perf}"
    response = requests.get(url)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    content = soup.find("main", class_="fullwidth")
    imp = content.select('div[id="content"] div[class="version"] div[class="section basics"] div[class="overview"] p a[class="verb-partner"]')
    if len(imp) == 0:
        return perf
    else:
        return imp[0].text.replace(chr(769), "").replace(chr(768), "")

def Get_Word_Info(word):
    """
    単語に関する情報を取得する関数
    """
    # 処理パイプライン
    doc = Doc(word)
    doc.segment(segmenter)
    doc.tag_morph(morph_tagger)
    doc.tokens[0].lemmatize(morph_vocab)
    return doc.tokens[0]

def Text_to_Wordlist(text):
    """
    文を解析して、原形に直された単語の集合を返す関数
    """
    # 処理パイプライン
    doc = Doc(text)
    doc.segment(segmenter)
    doc.tag_morph(morph_tagger)

    wordset = set()

    for token in doc.tokens:
        token.lemmatize(morph_vocab)
        wordset.add(token.lemma)
    
    return list(wordset)

def Generate_Yo_Variants(word):
    """
    е を ё と入れ替えて得られる全ての文字列を返す関数
    """
    indices = [i for i, c in enumerate(word) if c == 'е']
    variants = set()
    chars = list(word)
    for i in indices:
        chars[i] = 'ё'
        variants.add("".join(chars))
        chars[i] = "е"
    return variants

def Scraping_Words(word):
    """
    コトバンクから単語の該当するページを取得する関数
    """
    sleep(uniform(2, 4)) # 絶対に削除しない
    url = f"https://kotobank.jp/rujaword/{word}"
    response = requests.get(url)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")

    return soup

def Search_Page(word):
    """
    単語がコトバンクに存在するか調べる関数
    """
    # 文字列をエンコード
    encoded_word = quote(word)
    # ページを検索する
    page = Scraping_Words(encoded_word)
    title = page.find("title")
    if title.text == "コトバンク - お探しのページは見つかりません":
        return word, False
    else:
        return page, True

def Get_Meaning(page):
    """
    ページから単語の意味を取得する関数
    """
    meaning_section = page.find("section",class_="description")
    meaning_paragraphs = meaning_section.select("p[data-orgtag='meaning'], p[data-orgtag='example'], div[data-orgtag='subheadword']")

    replace_map = {chr(9312): "[1] ", chr(9313): "[2] ", chr(9314): "[3] ", chr(9315): "[4] ", chr(9316): "[5] ", chr(9317): "[6] ", chr(9318): "[7] ", chr(9319): "[8] ", chr(9320): "[9] ", chr(9321): "[10] ", chr(9322): "[11] ", chr(9323): "[12] ", chr(9324): "[13] ", chr(9325): "[14] ", chr(9326): "[15] ", chr(9327): "[16] ", chr(9328): "[17] ", chr(9329): "[18] ", chr(9330): "[19] ", chr(9331): "[20] "}
    meanings = ""

    for meaning in meaning_paragraphs:
        meaning = meaning.text.strip()
        meaning = meaning.replace("((", "[")
        meaning = meaning.replace("))", "]")
        meaning = re.sub("([А-ЯЁ])(//|‐)\\1", "\\1", meaning)
        meaning = meaning.replace("//", "")
        for k, v in replace_map.items():
            meaning = meaning.replace(k, v)
        meanings += f"{meaning}<br>"
    meanings = meanings[:len(meanings)-4]

    return meanings

def Get_Accent_Index(page):
    """
    ページからアクセント記号または ё を探して位置を返す関数
    """
    # 単語のアクセント位置を特定する
    header = page.find("div", class_="ex cf")
    header = header.select("h3")[0].text.split("[", 1)[0].strip()
    header = header.replace("|", "").replace(chr(768),"")
    accent = None
    # アクセント位置を記憶
    for i in range(len(header)):
        if ord(header[i]) == 769: # アクセント記号
            accent = i-1
            break
        elif header[i] == "ё":
            accent = i
            break
    return accent

def Redden_Accent(word, accent):
    """
    アクセント位置に色を付ける関数
    """
    # アクセント位置に色を付ける
    if accent is not None:
        return word[:accent] + f'<span style="color: rgb(255,0,0);">{word[accent]}</span>' + word[accent+1:]
    return word

def Same_Cards(word):
    """
    同じ単語のカードが既に存在するか確認する関数
    """
    matched_note = {"id": None}
    query = f'deck:"{config["deck_name"][deck_num]}"'
    note_ids = anki_connect_request("findNotes", query=query)
    if note_ids:
        info = anki_connect_request("notesInfo", notes=note_ids)
        for note in info:
            front_val = note["fields"][config[lang]["front"]]["value"]
            plain_text = BeautifulSoup(front_val, "html.parser").get_text()

            if plain_text.strip().lower() == word:
                matched_note["id"] = int(note["noteId"])
                matched_note[config[lang]["front"]] = word
                matched_note[config[lang]["back"]] = note["fields"][config[lang]["back"]]["value"]
                break
    return matched_note

##############################################################################################################
# カードの追加・更新に関する部分

def Add_Note(original_word, meaning, accent):
    """
    単語カードを新規登録する関数
    """
    # アクセント位置に色を付ける
    word = Redden_Accent(word=original_word, accent=accent)
    # カードを作成する
    note = {
        "deckName": config["deck_name"][deck_num],
        "modelName": config[lang]["modelName"],
        "fields": {
            config[lang]["front"]: word,
            config[lang]["back"] : meaning,
        },
        "options": {
            "allowDuplicate": False,
            "duplicateScope": "deck"
        },
        # "tags": ["RU-JP", "Word"]
    }
    result = anki_connect_request("addNote", note=note)
    if result:
        print(f"カードが新規作成されました　単語: {original_word}: ノートID: {result}")
        return True
    else:
        print("カードの新規作成に失敗しました")
        return False

def Update_Note(original_word, meaning, accent, id):
    """
    単語カードを上書きする関数
    """
    # アクセント位置に色を付ける
    word = Redden_Accent(word=original_word, accent=accent)
    # カードのフィールドを更新する
    note_id = id  # カードのIDを取得
    fields = {
        config[lang]["front"]: word,
        config[lang]["back"] : meaning,
    }
    note = {
        "id": note_id,
        "fields": fields
    }

    receive_None = anki_connect_request("updateNoteFields", note=note)
    after = anki_connect_request("notesInfo", notes=[id])[0]["fields"]

    if fields != after:
        print("カードが更新されました")
        return True
    else:
        print("カードの更新に失敗しました")
        return False

def Find_Notes(word):
    """
    単語が辞書に載っているか、載っているなら既に同じカードが存在するかを調べる関数
    該当ページなし        -> False
    同じ単語のカードが存在 -> 更新するか確認
    新しい単語            -> 単語カードを登録
    """

    # ロシア語でない単語をはじく
    if not is_russian(word):
        print("ロシア語ではない入力を受けたのでスキップします")
        return None

    page, page_exists = Search_Page(word)
    # ページが見つからなかった場合、表記ゆれを考慮して再検索
    if not page_exists:
        token = Get_Word_Info(page)
        if token.pos == "VERB" and token.feats["Aspect"] == "Perf":
            page, page_exists = Search_Page(Get_Imp_Form(word))
            if page_exists:
                word = token.lemma
            else:
                return False
        else:
            # е → ё の可能性を考慮した再検索
            alt_words = Generate_Yo_Variants(word)
            for alt in alt_words:
                page, page_exists = Search_Page(alt)
                if page_exists:
                    word = alt
                    break
            else:
                return False

    # アクセント位置を取得
    accent = Get_Accent_Index(page)
    # 意味を取得
    meaning = Get_Meaning(page)
    # 既に登録済みかを確認する
    matched_note = Same_Cards(word)

    return (matched_note, meaning, accent, word)

def Make_Notes(russian_words):
    """
    リスト内の単語を一つ一つカードにして登録する関数
    見つからなかった単語はリストにして返す
    """
    unfound_words = []
    for word in russian_words:
        result = Find_Notes(word=word)
        if result:
            matched_note, meaning, accent, word = result
            if matched_note["id"]:
                print(f'該当するカードが見つかりました　単語: {word}, ノートID: {matched_note["id"]}')
                if matched_note[config[lang]["back"]] != meaning:
                    print("見つかったカード：")
                    print(f'{config[lang]["front"]}: {matched_note[config[lang]["front"]]}')
                    print(f'{config[lang]["back"]}: {matched_note[config[lang]["back"]].replace("<br>", "\n")}\n')
                    print("スクレイピングした内容")
                    print(word)
                    print(meaning.replace("<br>", "\n"))
                    command = input("カードを更新しますか？(y/n)： ")
                    if command == "y":
                        Update_Note(original_word=word, meaning=meaning, accent=accent, id=matched_note["id"])
                    else: # if command == "n":
                        print("カードの更新をキャンセルしました")        
                else:
                    print("更新箇所がないので自動的にスキップします")
            else:
                Add_Note(original_word=word, meaning=meaning, accent=accent)
        else:
            if result is False:
                print(f"単語が見つかりませんでした　{word}")
                unfound_words.append(word)
    return unfound_words

def Random_Make_Note(q):
    """
    ランダムに単語を選び登録する関数
    """
    word = Random_Pick_Word()
    print(f"\n{word} が選ばれました")
    Make_Notes([word])
    if q == "n":
        check_meaning = input("意味を見ますか？(y/n)： ")
        if check_meaning == "y":
            print(Get_Meaning(Scraping_Words(word)).replace("<br>", "\n"))
            input("次の単語へ(Enter)")

def Get_Wordlist(filepath):
    with open(filepath, "w", encoding="utf-8") as f:
        for page_number in range(1, 645): 
            sleep(uniform(3,6)) # 最大 644 * 6秒 ~ 3900秒 ~ 1時間程度
            if page_number == 1:
                url = f"https://kotobank.jp/dictionary/prj/"
            else:
                url = f"https://kotobank.jp/dictionary/prj/{page_number}/"
            response = requests.get(url)
            response.encoding = "utf-8"
            page = BeautifulSoup(response.text, "html.parser")
            words_list = page.find("section", class_="list")
            words_list = words_list.find_all("li")
            for word in words_list:
                f.write(f"{word.text}\n")

def Find_Substrings(string):
    words = []
    filepath = os.path.join(os.path.dirname(__file__), "wordlist.txt")
    if not len(wordlist):
        if not os.path.exists(filepath):
            Get_Wordlist(filepath=filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            wordlist.update(f.readlines())
    words = [word.replace("\n", "") for word in wordlist if string in word]
    return words

def _main():
    """
    モード選択および選ばれたモードに対応した標準入力を要求する関数
    """
    global deck_num
    while True:
        print("-------モード一覧-------")
        # 上位分類を作るのもあり
        print("1：単語登録")
        print("2：その他")
        print("q：やめる")
        mode = input("モードを決めてください： ")
        if mode == "1":
            while True:
                print("\n<単語登録>")
                print("カードを追加するデッキ：", config["deck_name"][deck_num])
                print("f：ファイルから読み込み")
                print("i：キーボード入力から読み込み")
                print("p：部分一致検索して登録")
                print("r：コトバンクからランダム抽選")
                print("o：unfound_wordsを整理する")
                print("b：戻る")
                opt = input("オプションを選んでください： ")
                if opt == "o":
                    temp = config["input_file"]
                    config["input_file"] = config["output_file"]
                    russian_words = Read_File()
                    unfound_words = Make_Notes(russian_words)
                    if len(unfound_words) > 0:
                        Output_Unfound(unfound_words)            
                    config["input_file"] = temp
                elif opt == "f":
                    if config["input_file"] is None:
                        print("読み込みファイルが設定されていません")
                        Set_Input_File()
                        if config["input_file"] is None:
                            print("ファイルパスが入力されなかったため終了します")
                            exit(0)
                    russian_words = Read_File()
                    unfound_words = Make_Notes(russian_words)
                    if len(unfound_words) > 0:
                        Output_Unfound(unfound_words)
                elif opt == "i":
                    unfound_words = []
                    texts = []
                    while True:
                        text = input("単語または文を入力してください：")
                        if len(text) == 0:
                            break
                        texts.append(Normalize_Text(text))
                    wordset = Text_to_Wordlist(".".join(texts))
                    unfound_words = Make_Notes(wordset)
                    if len(unfound_words) > 0:
                        Output_Unfound(unfound_words)
                elif opt == "r":
                    n = int(input("何枚のカードを追加しますか？： "))
                    q = input("クイックモードにしますか？(y/n)： ")
                    if n > 0:
                        for _ in range(n):
                            Random_Make_Note(q)
                    else:
                        print("単語の追加をキャンセルしました")
                elif opt == "p":
                    texts = []
                    while True:
                        text = input("検索したい文字列を入力してください：")
                        if len(text) == 0:
                            break
                        print(Find_Substrings(text))
                    #     texts.extend(Find_Substrings(text))
                    # wordset = list(set(texts))
                    # null_dev = Make_Notes(wordset)
                elif opt == "b":
                    break
        elif mode == "2":
            while True:
                print("\n<その他>")
                print("c：カード追加先のデッキを変更する")
                print("s：設定の確認/変更")
                print("h：ヘルプを見る")
                print("b：戻る")
                opt = input("オプションを選んでください： ")
                if opt == "c":
                    Change_Deck()
                elif opt == "s":
                    Check_Config()
                    p = input("設定を変更しますか？(Y/n)")
                    if p == "Y":
                        print("設定を変更します")
                        Set_Config(0)
                        deck_num = config["deck_num"]-1
                        break
                elif opt == "h":
                    print(Help)
                    input("(Enterでオプション選択へ)")
                elif opt == "b":
                    break
        elif mode == "q":
            input("終了します(Enter)")
            Kill_Anki_Process()
            exit(0)

def main():
    """
    config.json のデータを読み込んでから main関数を始める
    """
    config = Read_Config()
    config["deck_name"] = Get_Deck_Name()
    Get_Deck_Version()
    _main()