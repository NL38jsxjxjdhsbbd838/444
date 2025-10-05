# пкпикапкиквк.py — готовый для Railway (user session, без input)
import os
import threading
import http.server
import socketserver
import random
from time import sleep
from telethon.sync import TelegramClient, errors
from telethon.errors.rpcerrorlist import MessageTooLongError, PeerIdInvalidError
from telethon.sessions import StringSession
from telethon.tl.patched import MessageService  # для фильтрации служебных сообщений

def mask(s):
    if not s: return None
    s = str(s)
    if len(s) <= 8:
        return s
    return s[:3] + "..." + s[-3:]

# --- Чтение переменных окружения ---
api_id_raw = os.environ.get("API_ID")
api_hash = os.environ.get("API_HASH")
session_string = os.environ.get("SESSION_STRING")
base_delay = int(os.environ.get("BASE_DELAY", "30"))
PORT = int(os.environ.get("PORT", 8080))

print("DEBUG: API_HASH:", mask(api_hash), flush=True)
print("DEBUG: SESSION_STRING present:", bool(session_string), flush=True)
print("DEBUG: BASE_DELAY:", base_delay, flush=True)
print("DEBUG: HTTP server will run on port:", PORT, flush=True)

if not api_id_raw or not api_hash:
    raise ValueError("API_ID или API_HASH не заданы в переменных окружения!")

try:
    api_id = int(api_id_raw)
except Exception:
    raise ValueError("API_ID должен быть числом!")

if not session_string:
    raise RuntimeError("SESSION_STRING не задан. Сгенерируй локально и добавь в env.")

# --- Создаём клиент до использования ---
client = TelegramClient(StringSession(session_string), api_id, api_hash)

EXCLUDED_GROUPS = [
    'Скупы UNION',
    'USF || Чат сливов',
    'Отзывы с продаж',
    'Отзывы с Тейвата',
    'STOP SCAM | КИДКИ | TRASH',
    'Гаранты Genshin Impact | SS PROJECT | GENSHIN | HSR | HONKAI | GARANTS',
    123456789
]

def dialog_sort(dialog):
    return getattr(dialog, 'unread_count', 0) or 0

def spammer(client):
    total_sent = 0

    # Получаем первое НЕслужебное сообщение из "Saved Messages"
    msg = None
    # Пробуем несколько последних сообщений, чтобы найти нормальное
    for m in client.iter_messages('me', limit=50):
        if isinstance(m, MessageService):
            continue
        # дополнительно: не пересылаем пустые сообщения
        if getattr(m, 'message', None) is None and not getattr(m, 'media', None):
            continue
        msg = m
        break

    if not msg:
        print("⚠️ В 'Saved Messages' нет подходящего сообщения для пересылки. Положи туда текст или медиа и перезапусти.", flush=True)
        return

    print(f"DEBUG: Выбрано сообщение для пересылки: id={msg.id}, text_preview={str(msg.message)[:80]}", flush=True)

    def create_groups_list():
        groups = []
        for dialog in client.iter_dialogs():
            if getattr(dialog, 'is_group', False) and getattr(dialog, 'unread_count', 0) >= 1:
                name = getattr(dialog, 'name', None)
                username = getattr(getattr(dialog, 'entity', None), 'username', None)
                if name in EXCLUDED_GROUPS or username in EXCLUDED_GROUPS or dialog.id in EXCLUDED_GROUPS:
                    continue
                groups.append(dialog)
        return groups

    print("🔁 Начинаем цикл рассылки...", flush=True)
    k = 0
    while True:
        print("DEBUG: Формируем список групп...", flush=True)
        groups = create_groups_list()
        print(f"DEBUG: Найдено {len(groups)} групп для обработки.", flush=True)
        groups.sort(key=dialog_sort, reverse=True)

        for g in groups:
            try:
                # Если по какой-то причине выбранное msg вдруг служебного типа — пропускаем
                if isinstance(msg, MessageService):
                    print("⚠️ Выбранное сообщение — служебного типа, пропускаем цикл.", flush=True)
                    break

                # Пытаемся переслать
                client.forward_messages(g, msg, 'me')
                target_name = g.name or getattr(g.entity, 'username', None) or str(g.id)
                print(f'✅ Отправлено в: {target_name}', flush=True)
                k += 1
                total_sent += 1

                delay_random = random.randint(5, 12)
                print(f'⏱ Пауза {delay_random} сек перед следующим сообщением...', flush=True)
                sleep(delay_random)

            except errors.ForbiddenError as o:
                try:
                    client.delete_dialog(g)
                except Exception:
                    pass
                print(f'⛔ ForbiddenError для {getattr(g, "name", g.id)} — удалена из списка. ({o})', flush=True)

            except errors.FloodError as e:
                secs = getattr(e, 'seconds', None)
                if secs:
                    print(f'🐢 FloodError: ожидание {secs} сек...', flush=True)
                    sleep(secs)
                else:
                    print(f'🐢 FloodError (без seconds) — ждать {base_delay} сек', flush=True)
                    sleep(base_delay)

            except PeerIdInvalidError:
                try:
                    client.delete_dialog(g)
                except Exception:
                    pass
                print(f'⚠️ PeerIdInvalidError — диалог удалён: {getattr(g, "name", g.id)}', flush=True)

            except MessageTooLongError:
                print(f'⚠️ MessageTooLongError для {getattr(g, "name", g.id)}', flush=True)

            except errors.BadRequestError as i:
                text_i = str(i)
                # Специально обрабатываем закрытые топики
                if "TOPIC_CLOSED" in text_i or "topic_closed" in text_i.lower():
                    print(f"⚠️ Пропускаем закрытую тему: {getattr(g, 'name', g.id)}", flush=True)
                    continue
                # Нельзя переслать некоторые типы сообщений — логируем и пропускаем
                if "Cannot forward messages" in text_i or "message type" in text_i.lower():
                    print(f"⚠️ Невозможно переслать (BadRequest): {text_i} — пропускаем {getattr(g, 'name', g.id)}", flush=True)
                    continue
                print(f'❗ BadRequestError: {i}', flush=True)

            except errors.RPCError as a:
                print(f'❗ RPCError: {a}', flush=True)

            except Exception as ex:
                # Ловим тип служебного сообщения, если Telethon бросил иначе
                txt = str(ex)
                if "Cannot forward messages" in txt or "MessageService" in txt:
                    print(f'⚠️ Пропускаем сообщение: {txt}', flush=True)
                    continue
                print("❗ Unexpected error:", ex, flush=True)

        print(f'Итог цикла: отправлено {k} сообщений в этом цикле. Всего отправлено: {total_sent}', flush=True)
        k = 0
        full_delay = base_delay + random.randint(2, 7)
        print(f'🔁 Пауза между циклами: {full_delay} сек...', flush=True)
        sleep(full_delay)

def run_server():
    class Handler(http.server.SimpleHTTPRequestHandler):
        pass
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"HTTP server running on port {PORT}", flush=True)
        httpd.serve_forever()

# --- Запускаем HTTP сервер в фоне ---
threading.Thread(target=run_server, daemon=True).start()

# --- Главное: подключаемся и запускаем spammer ---
if __name__ == "__main__":
    try:
        # Подключаемся к Telegram
        print("🔌 Подключаем client...", flush=True)
        client.connect()
        if not client.is_user_authorized():
            raise RuntimeError("Клиент не авторизован. Проверь SESSION_STRING.")
        print("✅ Клиент авторизован. Запускаем рассылку...", flush=True)

        spammer(client)

    except Exception as e:
        print("Fatal error:", e, flush=True)
    finally:
        try:
            client.disconnect()
        except Exception:
            pass

