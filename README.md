на данный момент готов скелет приложения, то есть реализована вставка, удаление, замена байт, сохранение изменеий, но это все не на уровне UI  
трtбования:  
- файл не хранится полностью в памяти(сделано: в каждый момент времени в памяти хранятся данные, считанные в буффер и несохраненные изменения)
- консольный интерфейс: 16 колонок байт, блок смещения и блок декодированных данных(работают над этим в данный момент, готов прототип, где можно подвигать курсором)
- возможность редактировать файл по колонке декодированных данных(не сделано)
- вставка, удаление, замена байт(на данный момент не поддерживается в UI)  

использовал модуль curses для UI, в линуксе он установлен сразу, в windows нужно устанавливать отдельно