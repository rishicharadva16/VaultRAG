import urllib.request
import json

req = urllib.request.Request(
    'http://localhost:8000/auth/login',
    data=json.dumps({'email': 'karan.shah@northwind.example', 'password': 'changeme123'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
res = urllib.request.urlopen(req)
token = json.loads(res.read())['access_token']

req2 = urllib.request.Request(
    'http://localhost:8000/ask',
    data=json.dumps({'question': 'What is the monthly logistics fee specified in the Apex contract?', 'top_k': 5}).encode('utf-8'),
    headers={'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
)
res2 = urllib.request.urlopen(req2)
data = json.loads(res2.read())
print('Refused:', data['refused'])
print('Answer:', data['answer'][:100])
for c in data['citations']:
    print(f"Citation [{c['id']}]: chunk_id={c['chunk_id']} file={c['file']} page={c['page']} highlights={c['highlights']}")
    print(f"  highlight_text: {repr(c['highlight_text'])}")
