# gunicorn.conf.py
import multiprocessing

# Force a long timeout so AI has time to think
timeout = 300  # 5 minutes
graceful_timeout = 60

# Use 'gthread' workers. This prevents the server from "freezing" 
# while waiting for Google/Tavily APIs.
worker_class = 'gthread'

# Concurrency settings
workers = 2
threads = 4

# Logging
loglevel = 'info'
accesslog = '-'
errorlog = '-'
