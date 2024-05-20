from __future__ import with_statement                                                           
 
import sys, contextlib, urllib
from urllib.parse import urlencode          
from urllib.request import urlopen
 
for url in sys.argv[1:]:
  request_url = 'http://tinyurl.com/api-create.php?' + urllib.parse.urlencode({'url':url})   
  with contextlib.closing(urllib.request.urlopen(request_url)) as response:   
    print(response.read().decode('utf-8 ')  ) 
                                 

