user = 'www-data'
group = 'www-data'
bind = '0.0.0.0:5001'
#workers = ${HDX_CKAN_WORKERS}
#access_log_format = '"%({x-real-ip}i)s" %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s"'
access_log_format = '%({x-real-ip}i)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(T)s %({host}i)s %({x-forwarded-proto}i)s'
accesslog = '/var/log/ckan/access.log'
errorlog = '/var/log/ckan/error.log'
loglevel = 'warning'
timeout = 120
graceful_timeout = 90
#worker_class = 'gevent'
