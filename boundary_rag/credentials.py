"""Explicit opt-in, read-only CC Switch import. Never serialize credentials."""
import json
import os
from pathlib import Path
import re
import sqlite3


def load_ccswitch(path=None):
    database = Path(path) if path else Path.home() / '.cc-switch' / 'cc-switch.db'
    with sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True) as connection:
        rows = connection.execute("SELECT settings_config, is_current FROM providers "
                                  "WHERE lower(name) = 'deepseek' ORDER BY is_current DESC").fetchall()
    if not rows:
        raise ValueError('No DeepSeek provider in CC Switch')
    settings = json.loads(rows[0][0])
    env = settings.get('env', {})
    base = env.get('ANTHROPIC_BASE_URL', '').rstrip('/')
    if base not in ('https://api.deepseek.com/anthropic', 'https://api.deepseek.com'):
        raise ValueError('CC Switch provider is not the official DeepSeek endpoint; configure environment explicitly')
    key = env.get('ANTHROPIC_AUTH_TOKEN', '')
    model = re.sub(r'\[[^\]]+\]$', '', env.get('ANTHROPIC_MODEL', ''))
    if not key or not model:
        raise ValueError('CC Switch DeepSeek key or model missing')
    os.environ['DEEPSEEK_API_KEY'] = key
    os.environ['DEEPSEEK_MODEL'] = model
    os.environ['DEEPSEEK_BASE_URL'] = 'https://api.deepseek.com'
