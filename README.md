# Async Crawler Assignment

## Установка

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```


## Запуск

```bash
python demo_day1.py
python demo_day2.py
python demo_day3.py
python demo_day4.py
python demo_day5.py
python demo_day6.py
python demo_day7.py
```

## CLI

```bash
python crawler.py --urls https://example.com --max-pages 10 --max-depth 2 --output results.jsonl --respect-robots --rate-limit 2
python crawler.py --config config.json
```

Поддерживаемые значения `--output`: `.jsonl`, `.json`, `.csv`, `.db`, `.sqlite`.
Для `.json` и `.jsonl` используется построчный JSON (JSONL).

## Конфигурация

Файл `config.json` содержит начальные URL, ссылки на sitemap,
ограничения, фильтры и настройки хранилища.
Параметры CLI переопределяют настройки конфигурации.

## API

- `AsyncCrawler.fetch_url(url)` возвращает HTML или пустую строку при ошибке.
- `AsyncCrawler.fetch_urls(urls)` загружает страницы конкурентно.
- `AsyncCrawler.fetch_and_parse(url)` возвращает данные страницы.
- `AsyncCrawler.crawl(start_urls, max_pages, ...)` обходит ссылки.
- `AdvancedCrawler.from_config(path)` создаёт краулер из JSON.
- `AdvancedCrawler.crawl()` использует начальные URL и sitemap из конфигурации.
- `AdvancedCrawler.get_stats()` возвращает статистику.
- `AdvancedCrawler.export_to_json(path)` и `export_to_html_report(path)` сохраняют отчёты.
- `close()` закрывает HTTP-сессию и хранилище.

JSONStorage сохраняет JSONL, CSVStorage — CSV, SQLiteStorage — SQLite.
База данных сохраняет вложенные поля links и metadata как JSON-строки.

## Тесты

```bash
python -m unittest discover -s tests -v
```
