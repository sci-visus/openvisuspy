import sys, contextlib, urllib
from urllib.parse import urlencode          
from urllib.request import urlopen

# ////////////////////////////////////////////////////////////////////////////
def ShortUlr(url):
  request_url = 'http://tinyurl.com/api-create.php?' + urllib.parse.urlencode({'url':url})   
  with contextlib.closing(urllib.request.urlopen(request_url)) as response:   
    return response.read().decode('utf-8 ')

for url in sys.argv[1:]:
  print(ShortUlr(url))

                                 

