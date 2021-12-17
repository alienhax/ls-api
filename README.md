# ls-api

working poc for LedgerScore crypto score calculation

using combination of Flask, gunicorn as Python 3.x wsgi http, NGINX web server 

run:
gunicorn --bind 0.0.0.0:5000 wsgi:app

daily cron to calculate scores:
#calculate all LS for unique wallet addr end of day
45 23 * * * /path/to/lsapp/microservices.py all
