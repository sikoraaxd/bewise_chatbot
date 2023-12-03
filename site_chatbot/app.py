import os
current_directory_path = os.path.abspath(os.getcwd())
import sys
sys.path.insert(1, os.path.join(current_directory_path, 'utils/'))

try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except:
    pass

import json
import streamlit as st
from dotenv import dotenv_values

import time

import openai
from preprocessor import get_index, roles_cleaner
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

import socks
import socket


config = dotenv_values(os.path.join(current_directory_path, '.env'))
DATABASE_FILE = os.path.join(current_directory_path, f"{config['DB_NAME']}")
OPENAI_KEY = config['OPENAI_KEY']
BOT_IMAGE_PATH = os.path.join(current_directory_path,'site_chatbot/assets/assistant_avatar.jpg')
DEFAULT_CONTEXT = config['DEFAULT_CONTEXT']
socks.set_default_proxy(socks.SOCKS5, config['SOCKS5_IP'], int(config['SOCKS5_PORT']), username=config['SOCKS5_USERNAME'], password=config['SOCKS5_PASSWORD'])
socket.socket = socks.socksocket

if "vectorstore" not in st.session_state:
    st.session_state['vectorstore'] = None

if "last_uploaded_files" not in st.session_state:
    st.session_state['last_uploaded_files'] = None

if "memory" not in st.session_state:
    st.session_state['memory'] = None

if "messages" not in st.session_state:
    st.session_state['messages'] = None

if "context" not in st.session_state:
    st.session_state['context'] = DEFAULT_CONTEXT

if "login" not in st.session_state:
    st.session_state['login'] = None

if 'page' not in st.session_state:
    st.session_state['page'] = 1


def to_chat(login):
    placeholder.empty()
    connection = create_connection(DATABASE_FILE)
    user_exist = check_user_existence(conn=connection, login=login)
    history = []
    if not user_exist:
        insert_user(connection, login, DEFAULT_CONTEXT, '[]')
    else:
        history = get_message_history(conn=connection, login=login)
        history = [json.loads(elem[0]) for elem in history]
        st.session_state['vectorstore'] = get_index(files=None, 
                                                    login=login, 
                                                    connection=connection, 
                                                    openai_api_key=OPENAI_KEY,
                                                    from_stored_data=True)
        context = get_user_context(conn=connection, 
                                   login=login)[0]
        st.session_state['context'] = context
    connection.close()
    st.session_state['memory'] = history.copy()
    st.session_state['messages'] = history.copy()
    st.session_state['login'] = login
    st.session_state['page'] += 1


def login():
    st.title("Введите свой логин")
    login = st.text_input('Логин')
    st.button('Вход', on_click=to_chat if len(login) else None, args=[login])


def clear_history(connection, login):
    connection = create_connection(DATABASE_FILE)
    st.session_state['messages'] = []
    st.session_state['memory'] = []
    clear_messages(conn=connection,
                   login=login)
    connection.close()


def chat():
    st.title("BEWISE.AI Умный ассистент")
    for message in st.session_state['messages']:
        with st.chat_message(message["role"], avatar= BOT_IMAGE_PATH if message['role'] == 'assistant' else None):
            st.markdown(message["text"])

    if prompt := st.chat_input("Прикрепите файлы и начните диалог!"):
        connection = create_connection(DATABASE_FILE)
        message_object = {
                'role':'user',
                'text': prompt
        }
        st.session_state['messages'].append(message_object)
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant", avatar=BOT_IMAGE_PATH):
            message_placeholder = st.empty()
            full_response = ""
            vectorstore = st.session_state.get("vectorstore")
            memory = st.session_state.get("memory")
            data_extract = ''
            if vectorstore is not None:
                search_results = vectorstore.similarity_search(prompt, k=3)
                data_extract = "/n ".join([result.page_content for result in search_results])
            
            memory.append(message_object)
            insert_message(conn=connection,
                        login=st.session_state['login'],
                        message=json.dumps(message_object)
            )
            #Составляем сообщение боту
            prompt_message = st.session_state['context']
            for elem in memory[-20:-1]:
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
            
            assistant_response = responce['choices'][0]['message']['content']
            assistant_response = roles_cleaner(assistant_response)

            message_object = {
                'role':'assistant',
                'text': assistant_response
            }
            memory.append(message_object)
            insert_message(conn=connection,
                        login=st.session_state['login'],
                        message=json.dumps(message_object)
            )

            st.session_state['memory'] = memory

            for chunk in assistant_response.split():
                full_response += chunk + " "
                time.sleep(0.05)
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        st.session_state['messages'].append({"role": "assistant", "text": full_response})

    with st.sidebar:
        uploaded_files = st.file_uploader("Выберите файл", accept_multiple_files=True)
        last_uploaded_files = st.session_state.get("last_uploaded_files")
        connection = create_connection(DATABASE_FILE)
        if uploaded_files and last_uploaded_files != uploaded_files:
            st.session_state['last_uploaded_files'] = uploaded_files
            vectorstore =  st.session_state.get("vectorstore")
            if vectorstore is not None:
                for id in vectorstore._collection.get()['ids']:
                    vectorstore._collection.delete(id)
            
            st.session_state['vectorstore'] = get_index(uploaded_files, 
                                                        login=st.session_state['login'], 
                                                        connection=connection, 
                                                        openai_api_key=OPENAI_KEY)
            st.session_state['memory'] = []
            
        context = st.text_input('Вы можете задать свой контекст')
        if len(context):
            context = context+'\n'
        else:
            context = DEFAULT_CONTEXT
        update_user_context(conn=connection, 
                            login=st.session_state['login'],
                            new_context=context)
        st.session_state['context'] = context
        connection.close()
        st.button('Очистить историю сообщений', on_click=clear_history, args=[connection, st.session_state['login']])
        
        

placeholder = st.empty()
with placeholder:
    with st.container():
        if st.session_state['page'] == 1:
            login()
        else:
            chat()