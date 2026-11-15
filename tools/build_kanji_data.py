#!/usr/bin/env python3
# かんじの へや: 学年ごとの漢字データ kanji/data/gN.json を作る
#
# つかいかた:
#   python3 -I tools/build_kanji_data.py            # 1〜4年をつくる（KanjiVG はなければダウンロード）
#   python3 -I tools/build_kanji_data.py --check    # つくらずに 例文と筆順を しらべるだけ
#   python3 -I tools/build_kanji_data.py --grades 1,2,3,4,5,6
#
# もとデータ（tools/kanji_src/）:
#   grades.json        学年別漢字配当表（平成29年告示、1026字）
#   joyo_school.json   常用漢字表（平成22年内閣告示）の 音訓と例。告示なので著作権の対象外
#   sentences/gN.txt   例文（1行1字。書き方は下の parse_line を見る）
# 筆順は KanjiVG（CC BY-SA 3.0, http://kanjivg.tagaini.net）。tools/.cache/kanjivg/ に置く。
# できた gN.json は筆順を含むので CC BY-SA 3.0 になる。
import argparse, json, os, re, sys, urllib.request
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'tools', 'kanji_src')
CACHE = os.path.join(ROOT, 'tools', '.cache', 'kanjivg')
OUT = os.path.join(ROOT, 'kanji', 'data')
KVG_URL = 'https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji/{}.svg'

KANJI_RE = re.compile(r'[㐀-鿿々]')
HIRA_RE = re.compile(r'^[ぁ-ゟー]+$')


def kata2hira(s):
    return ''.join(chr(ord(c) - 0x60) if 'ァ' <= c <= 'ヶ' else c for c in s)


DAKU = {}
for a, b in zip('かきくけこさしすせそたちつてとはひふへほ', 'がぎぐげござじずぜぞだぢづでどばびぶべぼ'):
    DAKU[a] = [b]
for a, b in zip('はひふへほ', 'ぱぴぷぺぽ'):
    DAKU[a].append(b)


def variants(r):
    """連濁（はな→ばな）と促音（がく→がっ）のゆれを足す"""
    out = {r}
    if r and r[0] in DAKU:
        out |= {d + r[1:] for d in DAKU[r[0]]}
    for x in list(out):
        if len(x) >= 2 and x[-1] in 'つくちきう':
            out.add(x[:-1] + 'っ')
    return out


def readings_of(entry):
    """常用漢字表の音訓から、例文の読みとして認めるもの（語幹とそのゆれ）を返す"""
    on, kun, ok = [], [], set()
    for y in entry['yomi']:
        r = y['r']
        if re.match(r'^[ァ-ヶー]+$', r):
            h = kata2hira(r)
            on.append(h)
            ok |= variants(h)
        else:
            kun.append(r)
            ok |= variants(r)
            for ex in y['ex']:
                m = re.match(r'^(\S)([ぁ-ゟ]+)$', ex)  # 生きる → 語幹 い
                if m and r.endswith(m.group(2)) and len(r) > len(m.group(2)):
                    ok |= variants(r[:-len(m.group(2))])
    return on, kun, ok


def load_strokes(k, fetch):
    name = '%05x' % ord(k)
    path = os.path.join(CACHE, name + '.svg')
    if not os.path.exists(path):
        if not fetch:
            return None
        os.makedirs(CACHE, exist_ok=True)
        with urllib.request.urlopen(KVG_URL.format(name), timeout=30) as r:
            data = r.read()
        with open(path, 'wb') as f:
            f.write(data)
    tree = ET.parse(path)
    strokes = []
    for el in tree.iter('{http://www.w3.org/2000/svg}path'):
        pid = el.get('id', '')
        m = re.search(r'-s(\d+)$', pid)
        if m:
            strokes.append((int(m.group(1)), el.get('d')))
    strokes.sort()
    return [d for _, d in strokes]


def parse_line(line):
    """
    1行 = 「字 例文 / 例文 / ...」
    例文 = 「文=よみ」または「文=よみ:字のよみ」
      文の中の [ ] が 問題にする ことば。送りがなも [ ] に入れてよい。
      よみ は [ ] の中ぜんぶの よみ（ひらがな）。
      字のよみ は 問題の字だけの よみ。[ ] が 字1つ（＋送りがな）なら 省略できる。
    例: 水 つめたい[水]をのむ=みず / プールで[水泳]をならう=すいえい:すい
        生 [生きる]ちからをそだてる=いきる
    """
    k, rest = line.split(None, 1)
    items = []
    for part in rest.split(' / '):
        part = part.strip()
        if not part:
            continue
        text, _, yy = part.rpartition('=')
        y, _, ky = yy.partition(':')
        items.append({'raw': part, 't': text.strip(), 'y': y.strip(), 'ky': ky.strip()})
    return k, items


def check_sentence(k, grade, s, grade_of, ok_readings, kun, errors, warns):
    t, y = s['t'], s['y']
    m = re.fullmatch(r'([^\[\]]*)\[([^\[\]]+)\]([^\[\]]*)', t)
    if not m:
        errors.append(f'{k}: [ ] がちょうど1組ない: {s["raw"]}')
        return None
    word = m.group(2)
    if k not in word:
        errors.append(f'{k}: [ ] の中に {k} がない: {s["raw"]}')
        return None
    if not y or not HIRA_RE.match(y):
        errors.append(f'{k}: よみ がひらがなでない: {s["raw"]}')
        return None
    for c in KANJI_RE.findall(t):
        if c == '々':
            continue
        g = grade_of.get(c)
        if g is None:
            errors.append(f'{k}: 小学校で習わない字「{c}」: {s["raw"]}')
        elif g > grade:
            errors.append(f'{k}: {grade}年の文に {g}年の字「{c}」: {s["raw"]}')
    # [ ] の中の かなは、同じ順番で よみ に出てくるはず。送りがなは よみ の さいご。
    kana_runs = re.findall(r'[\u3041-\u309f]+', word)
    pat = '.*'.join(re.escape(r) for r in kana_runs)
    if kana_runs and not re.search(pat, y):
        errors.append(f'{k}: [ ] の中の かな と よみ が合わない: {s["raw"]}')
        return None
    if re.search(r'[\u3041-\u309f]$', word) and not y.endswith(kana_runs[-1]):
        errors.append(f'{k}: 送りがな と よみ のおわりが合わない: {s["raw"]}')
        return None
    n_kanji = len(KANJI_RE.findall(word))
    if len(y) < n_kanji + sum(map(len, kana_runs)):
        errors.append(f'{k}: よみ が みじかすぎる: {s["raw"]}')
        return None
    ky = s['ky']
    tail = re.sub(r'^[^\u3041-\u309f]+', '', word)
    if not ky:
        tail = re.sub(r'^[^ぁ-ゟ]+', '', word)
        kanji_part = word[:len(word) - len(tail)]
        if kanji_part != k:
            errors.append(f'{k}: ことばが2字以上なので「:字のよみ」が要る: {s["raw"]}')
            return None
        if tail and not y.endswith(tail):
            errors.append(f'{k}: 送りがな「{tail}」と よみ が合わない: {s["raw"]}')
            return None
        ky = y[:len(y) - len(tail)] if tail else y
    if ky not in y:
        errors.append(f'{k}: 字のよみ「{ky}」が よみ「{y}」に ふくまれない: {s["raw"]}')
        return None
    post = m.group(3)
    if word == k and post:
        for r in kun:
            if r.startswith(ky) and r != ky and post.startswith(r[len(ky):]):
                errors.append(f'{k}: 送りがな「{r[len(ky):]}」を [ ] の中に入れる: {s["raw"]}')
                return None
    if ky not in ok_readings and (ky + tail) not in ok_readings:
        warns.append(f'{k}: 字のよみ「{ky}」が常用漢字表の音訓にない（特別な読み？）: {s["raw"]}')
        return {'t': t, 'y': y, 'ky': ky, 'sp': 1}  # sp: 特別な読み。書きの問題には出さない
    return {'t': t, 'y': y, 'ky': ky}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--grades', default='1,2,3,4')
    ap.add_argument('--no-fetch', action='store_true')
    args = ap.parse_args()
    grades = [int(x) for x in args.grades.split(',')]

    with open(os.path.join(SRC, 'grades.json'), encoding='utf-8') as f:
        glist = json.load(f)
    with open(os.path.join(SRC, 'joyo_school.json'), encoding='utf-8') as f:
        joyo = json.load(f)
    grade_of = {k: int(g) for g, ks in glist.items() for k in ks}

    errors, warns = [], []
    for g in grades:
        sent_path = os.path.join(SRC, 'sentences', f'g{g}.txt')
        sents = {}
        if os.path.exists(sent_path):
            with open(sent_path, encoding='utf-8') as f:
                for n, line in enumerate(f, 1):
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    k, items = parse_line(line)
                    if grade_of.get(k) != g:
                        errors.append(f'g{g}.txt:{n}: 「{k}」は{g}年の字ではない')
                        continue
                    if k in sents:
                        errors.append(f'g{g}.txt:{n}: 「{k}」が2回出てくる')
                    sents[k] = items
        out = []
        for k in glist[str(g)]:
            on, kun, ok = readings_of(joyo[k])
            strokes = load_strokes(k, fetch=not args.no_fetch and not args.check)
            if not strokes:
                errors.append(f'{k}: 筆順データがない')
            items = []
            for s in sents.get(k, []):
                r = check_sentence(k, g, s, grade_of, ok, kun, errors, warns)
                if r:
                    items.append(r)
            if len(items) < 2:
                warns.append(f'{k}: 例文が{len(items)}本しかない')
            out.append({'k': k, 'g': g, 'on': on, 'kun': kun, 'strokes': strokes or [], 'sentences': items})
        if not args.check:
            os.makedirs(OUT, exist_ok=True)
            with open(os.path.join(OUT, f'g{g}.json'), 'w', encoding='utf-8') as f:
                f.write('{"license":"strokes: KanjiVG (C) Ulrich Apel, CC BY-SA 3.0, http://kanjivg.tagaini.net",'
                        '"grade":%d,"kanji":[\n' % g)
                f.write(',\n'.join(json.dumps(e, ensure_ascii=False, separators=(',', ':')) for e in out))
                f.write('\n]}\n')
        n_sent = sum(len(e['sentences']) for e in out)
        print(f'{g}年: {len(out)}字, 例文 {n_sent}本')

    if not args.check:
        have = sorted(int(f[1:-5]) for f in os.listdir(OUT) if re.fullmatch(r'g\d\.json', f))
        with open(os.path.join(OUT, 'index.json'), 'w', encoding='utf-8') as f:
            json.dump({'grades': have}, f)
            f.write('\n')

    for w in warns:
        print('注意:', w)
    for e in errors:
        print('エラー:', e)
    print(f'エラー {len(errors)}件, 注意 {len(warns)}件')
    sys.exit(1 if errors else 0)


if __name__ == '__main__':
    main()
