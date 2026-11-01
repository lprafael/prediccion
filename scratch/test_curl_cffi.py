from curl_cffi import requests

try:
    r = requests.get('https://www.forebet.com/es/', impersonate='chrome120', timeout=15)
    print('curl_cffi status:', r.status_code, len(r.text))
    if 'rcnt' in r.text:
        print('SUCCESS: FOUND RCNT MATCH ROWS!')
    elif 'challenges.cloudflare.com' in r.text or 'cf-mitigated' in r.text:
        print('Cloudflare challenge present')
except Exception as e:
    print('curl_cffi error:', e)
