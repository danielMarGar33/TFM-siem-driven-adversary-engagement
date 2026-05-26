Lo ejecutas así:

python -m uvicorn webhook_server:app --host 127.0.0.1 --port 5000 --reload

Y tendrás estos dos hooks:

POST http://localhost:5000/translator
POST http://localhost:5000/engage-mapper