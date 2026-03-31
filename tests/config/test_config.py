import copy
import json
from pathlib import Path

import mootdx.config as config


def test_setup_creates_default_config_without_network_probe(tmp_path, monkeypatch):
    config_path = tmp_path / 'config.json'
    monkeypatch.setattr(config, 'CONF', str(config_path))
    monkeypatch.setattr(config, 'settings', {'SERVER': {}, 'BESTIP': {}, 'TDXDIR': 'broken'})

    expected = copy.deepcopy(config.DEFAULT_SETTINGS)

    assert config.setup() is True
    assert config.settings == expected
    assert config_path.exists()
    payload = json.loads(config_path.read_text(encoding='utf-8'))
    assert payload['TDXDIR'] == expected['TDXDIR']
    assert payload['BESTIP'] == expected['BESTIP']
    assert 'HQ' in payload['SERVER']
    assert 'EX' in payload['SERVER']
    assert 'GP' in payload['SERVER']


def test_setup_recovers_from_invalid_config_file(tmp_path, monkeypatch):
    config_path = tmp_path / 'config.json'
    config_path.write_text('not-json', encoding='utf-8')
    monkeypatch.setattr(config, 'CONF', str(config_path))
    monkeypatch.setattr(config, 'settings', {'SERVER': {}, 'BESTIP': {}, 'TDXDIR': 'broken'})

    expected = copy.deepcopy(config.DEFAULT_SETTINGS)

    assert config.setup() is True
    assert config.settings == expected
    payload = json.loads(config_path.read_text(encoding='utf-8'))
    assert payload['TDXDIR'] == expected['TDXDIR']
    assert payload['BESTIP'] == expected['BESTIP']
    assert 'HQ' in payload['SERVER']
    assert 'EX' in payload['SERVER']
    assert 'GP' in payload['SERVER']


def test_setup_loads_valid_config_and_keeps_defaults(tmp_path, monkeypatch):
    config_path = tmp_path / 'config.json'
    payload = {
        'BESTIP': {'HQ': ['1.2.3.4', 7709], 'EX': '', 'GP': ''},
        'TDXDIR': '/data/tdx',
    }
    config_path.write_text(json.dumps(payload), encoding='utf-8')
    monkeypatch.setattr(config, 'CONF', str(config_path))
    monkeypatch.setattr(config, 'settings', {'SERVER': {}, 'BESTIP': {}, 'TDXDIR': 'broken'})

    assert config.setup() is True
    assert config.settings['TDXDIR'] == '/data/tdx'
    assert config.settings['BESTIP']['HQ'] == ['1.2.3.4', 7709]
    assert config.settings['SERVER'] == config.DEFAULT_SETTINGS['SERVER']
    assert Path(config_path).exists()
