import os
current_directory_path = os.path.abspath(os.getcwd())
import sys
sys.path.insert(1, os.path.join(current_directory_path, 'utils/'))

import json
import streamlit as st
from dotenv import dotenv_values

import time
from preprocessor import (
    load_documents,
    get_vectorstore,
    retrieve,
    roles_cleaner, 
    convert_history_to_memory,
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

from langchain.chat_models import ChatOpenAI
from langchain.chains.question_answering import load_qa_chain
from langchain.memory import ConversationBufferWindowMemory

import socks
import socket


CONFIG = dotenv_values(os.path.join(current_directory_path, '.env'))
OPENAI_KEY = CONFIG['OPENAI_KEY']
BOT_IMAGE_PATH = os.path.join(current_directory_path,'site_chatbot/assets/assistant_avatar.jpg')
DEFAULT_CONTEXT = CONFIG['DEFAULT_CONTEXT']
socks.set_default_proxy(socks.SOCKS5, CONFIG['SOCKS5_IP'], int(CONFIG['SOCKS5_PORT']), username=CONFIG['SOCKS5_USERNAME'], password=CONFIG['SOCKS5_PASSWORD'])
socket.socket = socks.socksocket

if "vectorstore" not in st.session_state:
    st.session_state['vectorstore'] = None

if "last_uploaded_files" not in st.session_state:
    st.session_state['last_uploaded_files'] = None

if "memory" not in st.session_state:
    st.session_state['memory'] = ConversationBufferWindowMemory(k=20)

if "messages" not in st.session_state:
    st.session_state['messages'] = None

if "context" not in st.session_state:
    st.session_state['context'] = DEFAULT_CONTEXT

if "login" not in st.session_state:
    st.session_state['login'] = None

if 'page' not in st.session_state:
    st.session_state['page'] = 1

if 'model' not in st.session_state:
    st.session_state['model'] = load_qa_chain(
        ChatOpenAI(model='gpt-3.5-turbo-1106',
                   openai_api_key=CONFIG['OPENAI_KEY'],
                   temperature=0.8), 
        chain_type='stuff'
    )

def to_chat(login):
    placeholder.empty()
    connection = create_connection()
    user_exist = check_user_existence(
        conn=connection, 
        login=login
    )
    history = []

    if not user_exist:
        insert_user(connection, login, DEFAULT_CONTEXT)
    else:
        history = get_message_history(
            conn=connection, 
            login=login
        )
        history = [json.loads(elem[0]) for elem in history]
        context = get_user_context(
            conn=connection, 
            login=login
        )[0]
        st.session_state['context'] = context
    connection.close()

    data_path = os.path.join(current_directory_path, 'data', login)
    if login not in os.listdir(os.path.join(current_directory_path, 'data')):
        os.mkdir(data_path)

    docs = load_documents(data_path)
    try:
        vectorstore = get_vectorstore(
            documents=docs, 
            openai_api_key=CONFIG['OPENAI_KEY']
        )
    except:
        vectorstore = None
    st.session_state['vectorstore'] = vectorstore
    st.session_state['memory'] = convert_history_to_memory(history, st.session_state['memory'])
    st.session_state['messages'] = history.copy()
    st.session_state['login'] = login
    st.session_state['page'] += 1


def login():
    st.title("Введите свой логин")
    login = st.text_input('Логин')
    st.button('Вход', on_click=to_chat if len(login) else None, args=[login])


def clear_history(connection, login):
    connection = create_connection()
    st.session_state['messages'] = []
    st.session_state['memory'] = ConversationBufferWindowMemory(k=20)
    clear_messages(conn=connection,
                   login=login)
    connection.close()


def chat():
    st.title("BEWISE.AI Умный ассистент")
    
    for message in st.session_state['messages']:
        with st.chat_message(message["role"], avatar= BOT_IMAGE_PATH if message['role'] == 'assistant' else None):
            st.markdown(message["text"])

    if prompt := st.chat_input("Прикрепите файлы и начните диалог!"):
        connection = create_connection()
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
            retrieved = retrieve(
                query=prompt,
                vectorstore=vectorstore,
                memory=memory,
                context=st.session_state.get('context', CONFIG['DEFAULT_CONTEXT'])
            )
            insert_message(conn=connection,
                        login=st.session_state['login'],
                        message=json.dumps(message_object)
            )

            model = st.session_state['model']
            
            assistant_response = model.run(
                input_documents=retrieved,
                question=prompt
            )
            memory.save_context({'input': prompt}, {'output': assistant_response})

            message_object = {
                'role':'assistant',
                'text': assistant_response
            }
            insert_message(conn=connection,
                        login=st.session_state['login'],
                        message=json.dumps(message_object)
            )

            st.session_state['memory'] = memory
            for chunk in list(assistant_response):
                full_response += chunk
                time.sleep(0.01)
                message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(assistant_response)
        st.session_state['messages'].append({"role": "assistant", "text": assistant_response})

    with st.sidebar:
        uploaded_files = st.file_uploader("Выберите файл", accept_multiple_files=True)
        last_uploaded_files = st.session_state.get("last_uploaded_files")
        connection = create_connection()

        login = st.session_state['login']
        data_path = os.path.join(current_directory_path, 'data', login)
        if uploaded_files and last_uploaded_files != uploaded_files:
            
            st.session_state['last_uploaded_files'] = uploaded_files
            clear_files(data_path)
            save_files(
                files=uploaded_files,
                data_path=data_path
            )

            docs = load_documents(data_path)
            vectorstore = get_vectorstore(
                documents=docs, 
                openai_api_key=CONFIG['OPENAI_KEY']
            )
            st.session_state['vectorstore'] = vectorstore
            st.session_state['memory'] = ConversationBufferWindowMemory(k=20)
            
        context = st.text_input('Вы можете задать свой контекст')
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