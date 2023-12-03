import os
import subprocess
import argparse
import platform
from utils.sql import create_connection, create_tables
from dotenv import dotenv_values

if __name__ == '__main__':
    current_directory_path = os.path.dirname(os.path.abspath(__file__))
    config = dotenv_values(os.path.join(current_directory_path,'.env'))

    db_file = os.path.join(current_directory_path,config['DB_NAME'])
    connection = create_connection(db_file)
    if connection:
        create_tables(connection)
        connection.close()

    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--telegram', action='store_true', help='Запуск телеграма')
    parser.add_argument('-s', '--site', action='store_true', help='Запуск сайта')
    parser.add_argument('-a', '--all', action='store_true', help='Запуск обоих сервисов')
    
    args = parser.parse_args()
    processes = []
    current_os = platform.system()
    print('Обнаружена операционная система: ', current_os)
    run_command = 'python' if current_os == 'Windows' else 'python3'

    if args.all:
        print('Запуск сайта')
        site = subprocess.Popen(f'{run_command} -m streamlit run ./site_chatbot/app.py', shell=True)
        print('Запуск телеграм бота')
        telegram = subprocess.Popen(f'{run_command} ./telegram_chatbot/app.py', shell=True)
        processes.append(('site', site.pid))
        processes.append(('telegram', telegram.pid))
    elif args.site:
        print('Запуск сайта')
        site = subprocess.Popen(f'{run_command} -m streamlit run ./site_chatbot/app.py', shell=True)
        processes.append(('site', site.pid))
    elif args.telegram:
        print('Запуск телеграм бота')
        telegram = subprocess.Popen(f'{run_command} ./telegram_chatbot/app.py', shell=True)
        processes.append(('telegram', telegram.pid))

    if len(processes):
        dir_path = current_directory_path+'/processes'
        if 'processes' not in os.listdir(current_directory_path):
            os.mkdir(dir_path)
        for elem in processes:
            if current_os == 'Windows':
                with open(f'{dir_path}/{elem[0]}.bat', 'w') as f:
                    f.write(
                        f'''
                            @echo off
                            taskkill /PID {elem[1]} /T /F
                            if errorlevel 1 (
                                echo Ошибка при выполнении команды.
                            ) else (
                                del "%~f0"
                            )
                        '''
                    )
            elif current_os == 'Linux':
                with open(f'{dir_path}/{elem[0]}.sh', 'w') as f:
                    f.write(
                        f'''
                            #!/bin/bash

                            # Выполнение команды taskkill
                            pkill -P {elem[1]}

                            # Проверка кода возврата
                            if [ $? -eq 0 ]; then
                                # Удаление самого себя
                                rm -- "$0"
                            else
                                echo "Ошибка при выполнении команды."
                            fi
                        '''
                    )
