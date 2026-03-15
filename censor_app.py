# это главный файл нашего сайта для цензурирования текста
# этот файл содержит всю логику работы сайта
#
# что делает этот файл:
# 1. запускает веб-приложение
# 2. обрабатывает запросы от пользователей
# 3. цензурирует текст (заменяет мат на ***)
# 4. добавляет пояснения к сленговым словам
# 5. позволяет добавлять новые слова в списки

# импортируем библиотеку Flask (фреймворк для создания веб-сайтов на Python)

from flask import Flask, render_template, request, jsonify

# импортируем модуль для работы с регулярными выражениями
# регулярные выражения помогают искать и заменять нужные слова в тексте
import re

# импортируем модуль для работы с файлами
import os

# создаем приложение Flask
# app - это наш сайт, который мы создаем
app = Flask(__name__)

# мы будем хранить слова в обычных текстовых файлах
BAD_WORDS_FILE = 'bad_words.txt'   # файл с нецензурными словами
SLANG_WORDS_FILE = 'slang_words.txt'  # файл со сленговыми словами и их пояснениями
SAFE_WORDS_FILE = 'safe_words.txt'    # файл со "спасёнными" словами, которые нельзя цензурировать


def normalize_word(word):
    # вспомогательная функция для нормализации слова
    # убираем пробелы по краям и переводим в нижний регистр
    return word.strip().lower()


def get_russian_stem(word):
    # очень простая "стеммер"-функция для русского языка
    # она убирает самые частые окончания, чтобы мы могли находить разные формы одного и того же слова
    # это НЕ полноценная морфология, но для мата и сленга обычно хватает
    suffixes = [
        'иями', 'ями', 'ыми', 'ими', 'ыми',
        'ами',
        'ев', 'ов', 'ей', 'ям', 'ах', 'ях',
        'ия', 'ий', 'ое', 'ая', 'ую', 'ые', 'ых', 'их', 'ым', 'ом', 'ого', 'ему', 'ому',
        'ам', 'ем',
        'ые', 'ий', 'ый', 'ой',
        'ы', 'и', 'а', 'я', 'е', 'у', 'о', 'ю', 'ь'
    ]
    w = normalize_word(word)
    for suf in suffixes:
        if w.endswith(suf) and len(w) > len(suf) + 2:  # оставляем минимум 3 буквы в корне
            return w[:-len(suf)]
    return w


def words_match_by_form(text_word, base_word):
    # функция проверяет, относятся ли две формы к одному и тому же слову
    # пример: "хуя" и "хуй", "пизды" и "пизда"
    tw = normalize_word(text_word)
    bw = normalize_word(base_word)

    # точное совпадение
    if tw == bw:
        return True

    # сравнение по простому корню
    stem_t = get_russian_stem(tw)
    stem_b = get_russian_stem(bw)

    # точное совпадение корней
    if stem_t == stem_b and len(stem_t) >= 3:
        return True

    # дополнительная проверка для сленга: базовый корень может быть
    # внутри более длинного корня (например, "закринжевал" и "кринж")
    if len(stem_b) >= 4 and stem_b in stem_t:
        return True

    return False


def find_matching_slang(word, slang_dict):
    # находит подходящее сленговое слово по форме
    for base_word, explanation in slang_dict.items():
        if words_match_by_form(word, base_word):
            return base_word, explanation
    return None, None


def load_bad_words():
    # функция загружает список нецензурных слов и выражений из файла
    # читаем из файла все слова
    with open(BAD_WORDS_FILE, 'r', encoding='utf-8') as f:
        # читаем все строки, убираем пробелы и пустые строки
        words = [line.strip() for line in f.readlines() if line.strip()]
    return words


def load_slang_words():
    # функция загружает словарь сленговых слов из файла
    # читаем из файла все слова
    slang_dict = {}
    with open(SLANG_WORDS_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and '|' in line:
                # разделяем строку на слово и пояснение
                parts = line.split('|', 1)  # разделяем только по первому |
                if len(parts) == 2:
                    word = parts[0].strip()
                    explanation = parts[1].strip()
                    slang_dict[word] = explanation
    return slang_dict


def load_safe_words():
    # функция загружает список "безопасных" слов из файла
    # если файла нет, создаём его с одним базовым словом "употреблять"
    if not os.path.exists(SAFE_WORDS_FILE):
        with open(SAFE_WORDS_FILE, 'w', encoding='utf-8') as f:
            f.write('употреблять\n')

    with open(SAFE_WORDS_FILE, 'r', encoding='utf-8') as f:
        words = [line.strip() for line in f.readlines() if line.strip()]
    return words


def censor_text(text):
    # главная функция цензурирования текста
    bad_words = load_bad_words()
    slang_words = load_slang_words()
    safe_words = load_safe_words()

    # заранее считаем "корни" для всех списков
    bad_stems = {get_russian_stem(normalize_word(w)) for w in bad_words}
    safe_stems = {get_russian_stem(normalize_word(w)) for w in safe_words}

    # разбиваем текст на "слова" и "разделители", чтобы сохранить исходные пробелы и знаки препинания
    tokens = re.findall(r'\w+|\W+', text, flags=re.UNICODE)
    result_tokens = []

    for token in tokens:
        # если это "слово" (буквы/цифры), работаем с ним, иначе просто добавляем как есть
        if re.match(r'\w+', token, flags=re.UNICODE):
            original_token = token
            lowered = normalize_word(token)
            stem = get_russian_stem(lowered)

            # если корень слишком короткий, не считаем это ни матом, ни сленгом
            if len(stem) < 3:
                result_tokens.append(original_token)
                continue

            # "безопасные" слова никогда не трогаем
            if stem in safe_stems:
                result_tokens.append(original_token)
                continue

            # отдельные частые формы, которые должны быть матом,
            # даже если они не идеально попадают в стеммер
            if lowered in ('охуел', 'ахуе', 'нихуя'):
                result_tokens.append('***')
                continue

            # сначала проверяем, не является ли слово матом (по корню, только точное совпадение)
            if stem in bad_stems:
                result_tokens.append('***')
                continue

            # затем проверяем сленг (используем функцию, которая сравнивает формы аккуратнее)
            base_slang_word, explanation = find_matching_slang(lowered, slang_words)
            if base_slang_word is not None:
                # сохраняем исходное написание слова пользователя, но добавляем пояснение
                result_tokens.append(f'{original_token} ({explanation})')
            else:
                result_tokens.append(original_token)
        else:
            result_tokens.append(token)

    return ''.join(result_tokens)

def add_bad_word(word):
    # функция добавляет новое слово в файл и проверяет, не добавили ли его до этого

    word = word.strip().lower()  # убираем пробелы и делаем маленькими буквами
    
    # проверяем, что пользователь ввёл слово
    if not word:
        return False
    
    # загружаем существующие слова
    existing_words = load_bad_words()
    
    # проверяем, нет ли уже такого слова
    if word in existing_words:
        return False
    
    # добавляем новое слово в файл
    with open(BAD_WORDS_FILE, 'a', encoding='utf-8') as f:
        f.write(word + '\n')
    
    return True

def add_slang_word(word, explanation):

    # функция добавляет новое сленговое слово с пояснением в файл

    word = word.strip().lower()  # убираем пробелы и делаем маленькими буквами
    explanation = explanation.strip()  # убираем пробелы
    
    # проверяем, что слово и пояснение введены
    if not word or not explanation:
        return False
    
    # загружаем существующие слова
    existing_slang = load_slang_words()
    
    # Проверяем, нет ли уже такого слова
    if word in existing_slang:
        return False
    
    # Добавляем новое слово в файл
    with open(SLANG_WORDS_FILE, 'a', encoding='utf-8') as f:
        f.write(f'{word}|{explanation}\n')
    
    return True


# маршруты(routes) - это адреса на сайте, которые обрабатывают запросы пользователей

@app.route('/')
def index():
    # главная страница сайта, показывает пользователю HTML страницу с формой для ввода текста
    # когда пользователь заходит на главную страницу(localhost), Flask вызывает эту функцию и показывает файл templates/index.html

    return render_template('index.html')


@app.route('/filter', methods=['POST'])
def filter_text():
    # обработчик запроса на цензурирование текста
    #
    # что делает:
    # получает текст от пользователя
    # цензурирует его с помощью функции censor_text()
    # возвращает отцензурированный текст обратно
    # этот маршрут вызывается, когда пользователь нажимает кнопку "Отцензурировать"
    data = request.get_json()
    text = data.get('text', '')  # берем текст из запроса
    
    # цензурируем текст
    filtered_text = censor_text(text)
    
    # возвращаем результат в формате JSON (формат данных для веб-сайтов)
    return jsonify({'filtered_text': filtered_text})


@app.route('/add_bad_word', methods=['POST'])
def add_bad_word_route():
    # обработчик запроса на добавление нового матного слова
    # что делает:
    # получает слово от пользователя
    # добавляет его в файл bad_words.txt
    # возвращает сообщение об успехе или ошибке
    data = request.get_json()
    word = data.get('word', '').strip().lower()
    
    # проверяем, что слово введено
    if not word:
        return jsonify({
            'success': False,
            'message': 'Слово не может быть пустым'
        }), 400  # 400 - код ошибки "неправильный запрос"
    
    # добавляем(или понимаем, что оно уже добавлено) слово
    if add_bad_word(word):
        return jsonify({
            'success': True,
            'message': f'Слово "{word}" успешно добавлено в список нецензурных слов и выражений'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Это слово уже есть в списке или произошла ошибка'
        }), 400


@app.route('/add_slang_word', methods=['POST'])
def add_slang_word_route():
    # добавление нового сленгового слова
    data = request.get_json()
    word = data.get('word', '').strip().lower()
    explanation = data.get('explanation', '').strip()
    
    # проверяем, что слово и пояснение введены
    if not word or not explanation:
        return jsonify({
            'success': False,
            'message': 'Вы ничего не ввели'
        }), 400
    
    # добавляем слово или выясняем, что оно уже добавлено
    if add_slang_word(word, explanation):
        return jsonify({
            'success': True,
            'message': f'Слово "{word}" с пояснением "{explanation}" успешно добавлено'
        })
    else:
        return jsonify({
            'success': False,
            'message': 'Это слово уже есть в словаре или произошла ошибка'
        }), 400


@app.route('/get_slang_words', methods=['GET'])
def get_slang_words_route():
    # получение списка сленговых слов
    slang_words = load_slang_words()
    
    # преобразуем словарь в список словарей для удобства
    words_list = [{'word': word, 'explanation': explanation} 
                  for word, explanation in slang_words.items()]
    
    return jsonify({'slang_words': words_list})


if __name__ == '__main__':
    # создаем файлы со словами, если их еще нет
    load_bad_words()
    load_slang_words()
    
    # запускаем веб-сервер
    # debug=True означает, что при ошибках мы увидим подробную информацию
    # host='0.0.0.0' означает, что сайт будет доступен не только на этом компьютере
    # port=5000 - порт, на котором будет работать сайт
    app.run(debug=True, host='0.0.0.0', port=5000)