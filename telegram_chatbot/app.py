import os
current_directory_path = os.path.abspath(os.getcwd())
import sys
sys.path.insert(1, os.path.join(current_directory_path, 'utils/'))

import openai
import telebot
from telebot import types

from preprocessor import (
    load_documents,
    get_vectorstore,
    retrieve,
    roles_cleaner, 
    save_files,
    clear_files
)

from sql import (
    check_user_existence,
    create_connection,
    get_message_history,
    get_user_context,
    insert_message,
    insert_user,
    update_user_context,
    clear_messages
)

import io
from dotenv import dotenv_values

import socks
import socket


CONFIG = dotenv_values(os.path.join(current_directory_path,'.env'))
TELEBOT_TOKEN = CONFIG['TELEBOT_TOKEN']
OPENAI_KEY = CONFIG['OPENAI_KEY']
bot=telebot.TeleBot(TELEBOT_TOKEN)
DEFAULT_CONTEXT = CONFIG['DEFAULT_CONTEXT']

socks.set_default_proxy(socks.SOCKS5, CONFIG['SOCKS5_IP'], int(CONFIG['SOCKS5_PORT']), username=CONFIG['SOCKS5_USERNAME'], password=CONFIG['SOCKS5_PASSWORD'])
socket.socket = socks.socksocket


keyboard = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
context_button = types.KeyboardButton("Задать контекст")
clear_context_button = types.KeyboardButton("Сбросить контекст")
keyboard.add(context_button, clear_context_button)

chat_states = {}

def get_default_setup():
    return {
        'memory': [],
        'index': None,
        'setting_context': False,
        'context': DEFAULT_CONTEXT
    }


@bot.message_handler(func=lambda message: message.text == "Задать контекст")
def handle_context_button_click(message):
    bot.send_message(message.chat.id, "Ваше следующее сообщение станет контекстом запросов!")
    chat_states[message.chat.id]['setting_context'] = True


@bot.message_handler(func=lambda message: message.text == "Сбросить контекст")
def handle_clear_context_button_click(message):
    chat_states[message.chat.id]['setting_context'] = False
    chat_states[message.chat.id]['context'] = DEFAULT_CONTEXT
    chat_states[message.chat.id]['memory'] = []
    bot.send_message(message.chat.id, "Контекст сброшен!")

# Обработка начала работы с ботом
@bot.message_handler(commands=['start'])
def start_message(message):
    bot.send_message(message.chat.id,"Здравствуйте, я чат-бот компании Bewise.ai! Я могу проанализировать ваши документы!", reply_markup=keyboard)
    chat_states[message.chat.id] = get_default_setup()


#Обработка текстовых сообщений боту
@bot.message_handler(content_types='text')
def message_reply(message):
    if message.chat.id not in chat_states:
        chat_states[message.chat.id] = get_default_setup()
    
    if chat_states[message.chat.id]['setting_context']:
        chat_states[message.chat.id]['context'] = message.text
        chat_states[message.chat.id]['setting_context'] = False
        chat_states[message.chat.id]['memory'] = []
        bot.send_message(message.chat.id, f'"{message.text}" теперь является контекстом запросов!', reply_markup=keyboard)
    else:
        prompt = message.text
        data_extract = ''
        #Если ранее прислали документ для работы
        if chat_states[message.chat.id]['index'] is not None: 
            vectorstore = chat_states[message.chat.id]['index']
            search_results = vectorstore.similarity_search(prompt, k=3)
            data_extract = "/n ".join([result.page_content for result in search_results])

        chat_states[message.chat.id]['memory'].append({
            'role':'user',
            'text': prompt
        })

        #Составляем сообщение боту
        prompt_message = chat_states[message.chat.id]['context']
        for elem in chat_states[message.chat.id]['memory'][-20:-1]:
            prompt_message += f'{elem["role"]}: {elem["text"]}\n'
        
        prompt_message += f'''
            user: {prompt}
            {"Ответь на основе этого документа: " + data_extract if len(data_extract) else ''}
        '''

        responce = openai.ChatCompletion.create(
                                            api_key=OPENAI_KEY, 
                                            model='gpt-3.5-turbo-1106',
                                            temperature=0.7, 
                                            messages=[{
                                                'role': 'user',
                                                'content': prompt_message
                                            }])
        #Обработка ответа от чата гпт
        assistant_response = responce['choices'][0]['message']['content']
        assistant_response = roles_cleaner(assistant_response)
        
        chat_states[message.chat.id]['memory'].append({
                'role':'assistant',
                'text': assistant_response
        })

        bot.send_message(message.chat.id, assistant_response, reply_markup=keyboard)


#Обработка документов, присланных боту
@bot.message_handler(content_types=['document'])
def command_handle_document(message):
    try:
        file_info = bot.get_file(message.document.file_id)
        file_name = message.document.file_name
        downloaded_file = bot.download_file(file_info.file_path)

        if chat_states[message.chat.id]['index'] is not None:
            prev_index = chat_states[message.chat.id]['index']
            for id in prev_index._collection.get()['ids']:
                prev_index._collection.delete(id)

        index = get_index(file_name, io.BytesIO(downloaded_file), OPENAI_KEY)
        chat_states[message.chat.id]['index'] = index
        chat_states[message.chat.id]['memory'] = []
        bot.send_message(message.chat.id, "Готов работать с этим файлом!", reply_markup=keyboard)
    except Exception as e:
        print(e)
        bot.reply_to(message, "Произошла ошибка при обработке файла.")


bot.infinity_polling()