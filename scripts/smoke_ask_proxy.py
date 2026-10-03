"""DEV-only real HTTP + read-idle proxy smoke; never persists model answers."""
import os, sys, json, time, threading, http.client, tempfile
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from http.cookies import SimpleCookie
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, build_opener, ProxyHandler

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ['DJANGO_SETTINGS_MODULE']='config.settings.development'
os.environ['DB_NAME']='delisky_bi_dev'
import django
django.setup()
from django.conf import settings
from django.db import connection
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.core.wsgi import get_wsgi_application
from waitress import create_server
from apps.assistant.provider_factory import build_ask_delisky_provider
from apps.assistant.context_cache import clear_context_cache
from apps.assistant.models import AskDeliskyAuditEvent
from apps.assistant.local_provider import LocalAskDeliskyProvider
import apps.assistant.runtime as runtime

assert settings.DATABASES['default']['NAME']=='delisky_bi_dev'
with connection.cursor() as c:
    c.execute('SELECT current_database()')
    assert c.fetchone()[0]=='delisky_bi_dev'
assert settings.ASK_DELISKY_STREAMING_ENABLED
cfg=build_ask_delisky_provider()._config
assert cfg.timeout_seconds==180 and cfg.model_name=='qwen3:4b-instruct'
assert os.environ.get('ASK_DELISKY_REQUEST_TIMEOUT_SECONDS') is None
clear_context_cache()
with build_opener(ProxyHandler({})).open(Request(cfg.base_url+'/api/generate',
        data=json.dumps({'model':cfg.model_name,'keep_alive':0}).encode(),
        headers={'Content-Type':'application/json'}), timeout=30) as r:
    assert json.load(r).get('done')
print('DEV only; real WSGI HTTP; proxy read-idle timeout 125s; model unloaded',flush=True)
metrics={}
def measure(obj, name, label):
    original=getattr(obj,name)
    def wrapper(*args,**kwargs):
        start=time.perf_counter()
        try: return original(*args,**kwargs)
        finally:
            metrics[label]=time.perf_counter()-start
            metrics[label+'_calls']=metrics.get(label+'_calls',0)+1
            print(label,round(metrics[label],3),flush=True)
    setattr(obj,name,wrapper)
measure(runtime,'build_manager_insights','analytics_seconds')
measure(runtime,'get_manager_context','context_lookup_seconds')
measure(LocalAskDeliskyProvider,'generate','qwen_seconds')

server=create_server(get_wsgi_application(), host='127.0.0.1',port=0,threads=4)
threading.Thread(target=server.run,daemon=True).start()
origin_port=int(server.effective_port)
class IdleProxy(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self): self.forward()
    def do_POST(self): self.forward()
    def forward(self):
        upstream=http.client.HTTPConnection('127.0.0.1',origin_port,timeout=125)
        body=self.rfile.read(int(self.headers.get('Content-Length','0')))
        try:
            headers={k:v for k,v in self.headers.items() if k.lower() not in {'connection','host'}}
            headers['Host']='localhost'
            upstream.request(self.command,self.path,body=body,headers=headers)
            response=upstream.getresponse()
            self.send_response(response.status)
            for k,v in response.getheaders():
                if k.lower() not in {'transfer-encoding','connection','content-length','server','date'}:
                    self.send_header(k,v)
            self.end_headers()
            self.wfile.flush()
            while True:
                chunk=response.read1(4096)
                if not chunk: break
                self.wfile.write(chunk)
                self.wfile.flush()
        finally:
            upstream.close()
proxy=ThreadingHTTPServer(('127.0.0.1',0),IdleProxy)
threading.Thread(target=proxy.serve_forever,daemon=True).start()

user=get_user_model().objects.get(username='rachidone1')
client=Client()
client.force_login(user)
cookies=SimpleCookie()
cookies[settings.SESSION_COOKIE_NAME]=client.cookies[settings.SESSION_COOKIE_NAME].value
def cookie_header(): return '; '.join(f'{k}={v.value}' for k,v in cookies.items())
conn=http.client.HTTPConnection('127.0.0.1',proxy.server_port,timeout=125)
conn.request('GET',reverse('dashboard:manager_tool',args=['ask-delisky']),headers={'Cookie':cookie_header()})
response=conn.getresponse()
assert response.status==200
for k,v in response.getheaders():
    if k.lower()=='set-cookie': cookies.load(v)
response.read();conn.close()
report={'db':'delisky_bi_dev','user':'rachidone1','model':cfg.model_name,'provider_timeout':cfg.timeout_seconds,'proxy_read_idle_seconds':125,'runs':[]}
for mode in ['cold','warm']:
    metrics={'analytics_seconds':0,'analytics_seconds_calls':0}
    data=urlencode({'question':'اذكر ملاحظة تحليلية واحدة مدعومة بالمؤشرات في السياق مع الدليل وحدود الاستنتاج.',
                    'period_start':'2026-04-04','period_end':'2026-08-26'})
    before=AskDeliskyAuditEvent.objects.count()
    conn=http.client.HTTPConnection('127.0.0.1',proxy.server_port,timeout=125)
    start=time.perf_counter()
    conn.request('POST',reverse('dashboard:ask_delisky'),body=data,headers={
        'Cookie':cookie_header(),'X-CSRFToken':cookies[settings.CSRF_COOKIE_NAME].value,
        'Content-Type':'application/x-www-form-urlencoded','Accept':'text/event-stream',
    })
    response=conn.getresponse()
    metrics['http_headers_seconds']=time.perf_counter()-start
    assert response.status==200 and response.getheader('Content-Type').startswith('text/event-stream')
    times=[];event=None;payload=None;completed=False
    while True:
        line=response.readline()
        if not line: break
        if line.startswith(b'event: '): event=line.decode().strip()[7:]
        if line.startswith(b'data: '): payload=json.loads(line[6:])
        if line==b'\n':
            now=time.perf_counter()-start
            times.append(now)
            print(mode,event,round(now,3),flush=True)
            if event in {'result','error'}:
                assert event=='result' and payload['ok'],payload.get('error')
                assert payload['answer'].strip()
                completed=True
                metrics['answer_characters']=len(payload['answer'])
                # Discard answer immediately; report retains only timing/counts.
                payload=None
    assert completed, 'Stream ended without a terminal result'
    metrics.update(mode=mode,first_event_seconds=times[0],max_response_gap_seconds=max(b-a for a,b in zip([0]+times,times)),completion_seconds=time.perf_counter()-start,event_count=len(times))
    conn.close()
    assert AskDeliskyAuditEvent.objects.count()==before+1
    assert AskDeliskyAuditEvent.objects.latest('pk').outcome=='SUCCESS'
    assert metrics['first_event_seconds']<5 and metrics['max_response_gap_seconds']<20
    if mode=='cold': assert metrics['completion_seconds']>125
    else: assert metrics['analytics_seconds_calls']==0
    report['runs'].append(metrics.copy())
    (Path(tempfile.gettempdir()) / 'delisky_proxy_smoke_results.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(metrics),flush=True)
client.logout()
proxy.shutdown()
server.close()
print('PASS',flush=True)
