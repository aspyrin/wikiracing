ignore_patterns = [
    'Вікіпедія:',
    'Довідка:',
    'Збільшити',
    'Категорія:',
    'Обговорення:',
    'Обговорення шаблону:',
    'Перегляд цього шаблону',
    'Редагувати розділ:',
    'Шаблон:',
    'commons:',
    'd:',
    'en:',
    'q:Головна стаття',
    'q:Special:Search/',
    'w:'
]


def check_pattern_in_title(page_title: str) -> bool:
    result: bool = False
    for pat in ignore_patterns:
        if page_title.find(pat) != -1:
            result = True
    return result
