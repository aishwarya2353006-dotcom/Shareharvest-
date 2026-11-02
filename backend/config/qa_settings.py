import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured

from config.settings import *


qa_database = os.environ.get('SHAREHARVEST_QA_DB')
if not qa_database:
    raise ImproperlyConfigured('SHAREHARVEST_QA_DB must point to an isolated QA database.')

qa_database_path = Path(qa_database).resolve()
development_database_path = (BASE_DIR / 'db.sqlite3').resolve()
if qa_database_path == development_database_path:
    raise ImproperlyConfigured('The QA database cannot be the development database.')

DATABASES['default']['NAME'] = qa_database_path
