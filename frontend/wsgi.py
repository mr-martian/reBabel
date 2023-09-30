import os
import sys

os.environ['DJANGO_SETTINGS_MODULE'] = 'frontend.settings'

root = os.path.dirname(__file__)
if root not in sys.path:
    sys.path.append(root)

from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
