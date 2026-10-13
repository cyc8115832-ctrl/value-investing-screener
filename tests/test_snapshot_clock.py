import json
from datetime import date
import pytest
from scripts import verify_static_snapshot as verifier
from src.services import market_evidence, time_series
from src.web.api import verified_routes


@pytest.mark.parametrize('fail', [False, True])
def test_snapshot_clock_uses_saved_day_and_is_restored(tmp_path, monkeypatch, fail):
    (tmp_path/'snapshot-manifest.json').write_text(json.dumps({'generated_at': '2026-10-08T20:00:00Z'}), encoding='utf-8')
    modules=(market_evidence,time_series,verified_routes)
    original=[module.taiwan_today for module in modules]

    def compare(directory):
        assert all(module.taiwan_today()==date(2026,10,9) for module in modules)
        if fail:
            raise ValueError('comparison failed')
        return {'checks_passed': True}

    monkeypatch.setattr(verifier,'_verify_static_snapshot',compare)
    if fail:
        with pytest.raises(ValueError):
            verifier.verify_static_snapshot(tmp_path)
    else:
        result=verifier.verify_static_snapshot(tmp_path)
        assert result['comparison_as_of_date']=='2026-10-09'
        assert result['freshness_verified'] is False
    assert all(module.taiwan_today is clock for module,clock in zip(modules,original))
